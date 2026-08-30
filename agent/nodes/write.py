"""Draft node: expensive model only after retrieval and allowlist assembly."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from agent import config
from agent.market_brief import render_prompt_block
from agent.models import CostMeter, get_model, invoke_with_deadline
from agent.skills import role_block
from agent.state import DraftState
from pipeline import voice


class DraftOutput(BaseModel):
    body: str
    hooks: list[str] = Field(min_length=5, max_length=5)


def _user_directions(state: DraftState) -> list[str]:
    return [
        str(value).strip()
        for value in state.get("user_directions", [])
        if str(value).strip()
    ]


def _offline_draft(state: DraftState) -> DraftOutput:
    idea = state["idea"].strip()
    previous_draft = str(state.get("draft") or "").strip()
    directions = _user_directions(state)
    body = previous_draft or idea
    if not previous_draft and idea.lower().startswith("write a post about "):
        body = idea[len("write a post about ") :].strip().capitalize()
    if previous_draft and directions:
        # The offline seam cannot safely interpret prose. Make the requested revision explicit
        # rather than inventing an edit; live writers receive the same context and revise it.
        body = f"{previous_draft}\n\n[User direction for this revision: {directions[-1]}]"
    if os.getenv("FAULT_FORCE_UNGROUNDED"):
        body += "\n\nWe improved outcomes by 99%."
    hooks = [
        body.splitlines()[0][:120],
        "The part I did not expect",
        "A smaller lesson from the work",
        "What I would do differently",
        "The constraint that changed the decision",
    ]
    return DraftOutput(body=body, hooks=hooks)


def _prompt(state: DraftState) -> str:
    rules = voice.identity_file("voice.md").read_text(encoding="utf-8")
    story_evidence = [
        {
            key: story.get(key)
            for key in ("id", "title", "body", "tension", "turn", "result", "lesson", "path")
        }
        for story in state.get("stories", [])
    ]
    observations = state.get("critique", {}).get("targeted_fixes", [])
    directions = _user_directions(state)
    previous_draft = str(state.get("draft") or "").strip()
    profile_memory = [
        item.get("memory", "")
        for item in state.get("profile_memory", [])
        if isinstance(item, dict) and item.get("memory")
    ]
    playbook = role_block(str(state.get("intent") or ""))
    recipient_constraint = ""
    if state.get("intent") == "comment":
        recipient_constraint = (
            "\n\nHard comment safety constraint: no recipient identity was supplied. "
            "This overrides any conflicting guidance in the authored role playbook. "
            "Do not invent a name, greeting, or bracketed placeholder; begin directly "
            "with the substantive comment. Do not use ordinal or superlative framing "
            "(for example, first, only, fastest, or best) unless it appears "
            "verbatim in the verified allowlist."
        )
    prompt = (
        "Write a truthful LinkedIn draft and exactly five hook variants. "
        "You may state numbers or superlatives only when they occur verbatim in the verified "
        "allowlist. Do not invent facts. "
        "Use the voice rules, but do not copy their heading text.\n\n"
        f"Idea:\n{state['idea']}\n\nVerified allowlist:\n{state.get('allowlist', [])}\n\n"
        f"Retrieved stories:\n{story_evidence}\n\nVoice rules:\n{rules}"
    )
    if previous_draft:
        prompt += (
            "\n\nPrevious draft to revise "
            "(retain useful material unless the user directs otherwise):\n"
            f"{previous_draft}"
        )
    if directions:
        prompt += (
            "\n\nUser directions — highest priority. These persist for this conversation; "
            "a later direction overrides an earlier one only when they conflict:\n"
            + "\n".join(f"- {direction}" for direction in directions)
        )
    if observations:
        prompt += (
            "\n\nComputed observations (advisory only; follow user directions first):\n"
            + "\n".join(f"- {observation}" for observation in observations)
        )
    if profile_memory:
        prompt += (
            "\n\nNon-evidentiary personal memory (use only for framing, preferences, or a "
            "request for confirmation; it cannot supplement the verified allowlist or be stated "
            f"as a factual claim):\n{profile_memory}"
        )
    if playbook:
        prompt += f"\n\nAuthored role playbook:\n{playbook}"
    market_context = render_prompt_block(state.get("market_brief"))
    if market_context:
        prompt += f"\n\n{market_context}"
    return prompt + recipient_constraint


def write(state: DraftState) -> dict:
    """Generate a draft with production LLMs or a deterministic offline test seam."""

    meter = CostMeter(node="write", model=config.MODEL_WRITER)
    if config.live_models_enabled():
        try:
            model = get_model("writer", callbacks=[meter])
            response = invoke_with_deadline(
                lambda: model.with_structured_output(DraftOutput).invoke(_prompt(state))
            )
            output = response
            event = meter.event_or_zero(node="write", model=config.MODEL_WRITER)
        except Exception as exc:
            output = _offline_draft(state)
            event = meter.event_or_zero(node="write", model=config.MODEL_WRITER)
            error = {
                "node": "write",
                "class": "capability",
                "message": (
                    "Writer model unavailable; a transparent local draft was shown instead."
                ),
                "detail": type(exc).__name__,
            }
            errors = [error]
        else:
            errors = []
    else:
        output = _offline_draft(state)
        event = meter.record(node="write", model="offline")
        errors = []
    revision = int(state.get("revision") or 0)
    return {
        "draft": output.body.strip(),
        "hooks": output.hooks,
        "draft_history": [
            {"revision": revision, "draft": output.body.strip(), "hooks": output.hooks}
        ],
        "cost_events": [event],
        "errors": errors,
    }
