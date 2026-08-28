"""Draft node: expensive model only after retrieval and allowlist assembly."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from agent import config
from agent.market_brief import render_prompt_block
from agent.models import CostMeter, get_model
from agent.state import DraftState
from pipeline import voice


class DraftOutput(BaseModel):
    body: str
    hooks: list[str] = Field(min_length=5, max_length=5)


def _offline_draft(state: DraftState) -> DraftOutput:
    idea = state["idea"].strip()
    body = idea
    if idea.lower().startswith("write a post about "):
        body = idea[len("write a post about ") :].strip().capitalize()
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
    revisions = state.get("critique", {}).get("targeted_fixes", [])
    prompt = (
        "Write a truthful LinkedIn draft and exactly five hook variants. "
        "You may state numbers or superlatives only when they occur verbatim in the verified "
        "allowlist. Do not invent facts. "
        "Use the voice rules, but do not copy their heading text.\n\n"
        f"Idea:\n{state['idea']}\n\nVerified allowlist:\n{state.get('allowlist', [])}\n\n"
        f"Retrieved stories:\n{story_evidence}\n\nVoice rules:\n{rules}\n\n"
        f"Targeted fixes for this revision:\n{revisions}"
    )
    market_context = render_prompt_block(state.get("market_brief"))
    return prompt + (f"\n\n{market_context}" if market_context else "")


def write(state: DraftState) -> dict:
    """Generate a draft with production LLMs or a deterministic offline test seam."""

    meter = CostMeter(node="write", model=config.MODEL_WRITER)
    if config.live_models_enabled():
        try:
            model = get_model("writer", callbacks=[meter])
            response = model.with_structured_output(DraftOutput).invoke(_prompt(state))
            output = response
            event = meter.event_or_zero(node="write", model=config.MODEL_WRITER)
        except Exception as exc:
            output = _offline_draft(state)
            event = meter.event_or_zero(node="write", model=config.MODEL_WRITER)
            error = {
                "node": "write",
                "class": "capability",
                "message": (
                    "Writer model unavailable; escalating instead of queueing "
                    "a placeholder draft as if it were generated."
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
