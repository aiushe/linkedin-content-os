"""Read-only grounding node with explicit degradation and capability boundaries."""

from __future__ import annotations

from typing import Any

from agent import config
from agent.errors import AgentFailure, FailureClass
from agent.models import CostMeter, get_model
from agent.state import DraftState
from agent.tools import (
    find_viral_posts_read,
    get_allowlist_read,
    get_read_tools,
    get_template_read,
    retrying_story_search,
    web_search_read,
)
from pipeline import common


def _hydrate_stories(stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach story bodies to retrieval hits so the writer sees inspectable evidence."""

    by_id = {str(story.get("id")): story for story in common.load_stories()}
    return [{**story, **by_id.get(str(story.get("id")), {})} for story in stories]


def _run_live_react(idea: str, meter: CostMeter) -> None:
    """Run the bounded read-only ReAct loop for traceable live grounding.

    Structured state is still built from the same wrappers below, preventing a model
    from omitting evidence or inventing an object shape.
    """

    from langchain.agents import create_agent

    system_prompt = (
        "You are a retrieval-only grounding agent for LinkedIn content. Use only the provided "
        "read tools. Do not draft a post, do not suggest unpublished facts, and do not call any "
        "write action. Retrieve evidence useful for the user's requested idea."
    )
    create_agent(
        get_model("router", callbacks=[meter]), get_read_tools(), system_prompt=system_prompt
    ).invoke({"messages": [{"role": "user", "content": idea}]})


def ground(state: DraftState) -> dict:
    """Retrieve stories and facts; empty intel degrades, empty stories escalates."""

    reasons: list[str] = []
    errors: list[dict[str, str]] = []
    degraded = False
    meter = CostMeter(node="ground", model=config.MODEL_ROUTER)
    if config.live_models_enabled():
        try:
            _run_live_react(state["idea"], meter)
            cost_events = [meter.event_or_zero(node="ground", model=config.MODEL_ROUTER)]
        except Exception as exc:
            degraded = True
            reasons.append(f"Grounding ReAct trace unavailable: {type(exc).__name__}.")
            errors.append(
                {
                    "node": "ground",
                    "class": FailureClass.DEGRADABLE.value,
                    "message": "Grounding ReAct trace failed; deterministic retrieval continued.",
                    "detail": type(exc).__name__,
                }
            )
            cost_events = [meter.event_or_zero(node="ground", model=config.MODEL_ROUTER)]
    else:
        cost_events = [meter.record(node="ground", model="offline")]

    try:
        stories = _hydrate_stories(retrying_story_search(state["idea"]))
    except AgentFailure as failure:
        stories = []
        errors.append(failure.as_record(node="ground"))
    if not stories:
        errors.append(
            {
                "node": "ground",
                "class": FailureClass.CAPABILITY.value,
                "message": "Story retrieval returned no grounded records.",
                "detail": "Build the story index or add a story before drafting.",
            }
        )
        return {
            "stories": [],
            "allowlist": get_allowlist_read(),
            "template": None,
            "grounding_degraded": degraded,
            "degradation_reasons": reasons,
            "errors": errors,
            "cost_events": cost_events,
            "terminal_reason": "Capability failure: no story index.",
        }

    allowlist = get_allowlist_read()
    template = None
    try:
        viral_posts = find_viral_posts_read(state["idea"], k=5)
    except Exception as exc:
        viral_posts = []
        degraded = True
        reasons.append(f"Market intel unavailable: {type(exc).__name__}.")
    if viral_posts:
        template_id = next(
            (
                post.get("template_id")
                for post in viral_posts
                if isinstance(post.get("template_id"), int)
            ),
            None,
        )
        if template_id is not None:
            template = get_template_read(template_id)
    if not template:
        degraded = True
        reasons.append("No local market template was available; drafted from stories only.")
        errors.append(
            {
                "node": "ground",
                "class": FailureClass.DEGRADABLE.value,
                "message": "No local market template was available.",
                "detail": "Continuing with retrieved stories only.",
            }
        )
    try:
        web_search_read(state["idea"])
    except AgentFailure as failure:
        if failure.failure_class == FailureClass.TRANSIENT:
            degraded = True
            reasons.append("Optional web search failed after retries; continuing without it.")
            errors.append(failure.as_record(node="ground"))
        else:
            errors.append(failure.as_record(node="ground"))
    return {
        "stories": stories,
        "allowlist": allowlist,
        "template": template,
        "grounding_degraded": degraded,
        "degradation_reasons": reasons,
        "errors": errors,
        "cost_events": cost_events,
    }
