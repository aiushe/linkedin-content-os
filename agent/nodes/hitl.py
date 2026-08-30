"""Interrupt payload and resume handling for the only write boundary."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from agent.state import DraftState

VALID_ACTIONS = {"approve", "edit", "reject", "retry", "escalate", "annotate"}


def _review_payload(state: DraftState) -> dict[str, Any]:
    cost_events = state.get("cost_events", [])
    running_cost_usd = round(
        sum(float(event.get("usd") or 0) for event in cost_events if isinstance(event, dict)), 8
    )
    return {
        "task": "Review grounded LinkedIn draft before it can enter drafts/queue/.",
        "draft": state.get("draft", ""),
        "hooks": state.get("hooks", []),
        "gate_verdict": state.get("gate_verdict"),
        "voice_report": state.get("voice_report", {}),
        "claims_report": state.get("claims_report", {}),
        "confidential_report": state.get("confidential_report", {}),
        "evidence": [
            {"id": story.get("id"), "title": story.get("title"), "path": story.get("path")}
            for story in state.get("stories", [])
        ],
        "revision": state.get("revision", 0),
        "market_brief": {
            "available": state.get("market_brief", {}).get("available", False),
            "topic": state.get("market_brief", {}).get("topic", ""),
            "exemplars": state.get("market_brief", {}).get("exemplars", []),
            "estimated_usd": state.get("market_brief", {}).get("estimated_usd", 0.0),
        }
        if isinstance(state.get("market_brief"), dict)
        else {},
        "cost_events": cost_events,
        "running_cost_usd": running_cost_usd,
        "actions": sorted(VALID_ACTIONS),
    }


def hitl(state: DraftState) -> dict:
    """Pause graph execution and normalize the reviewer's six possible actions."""

    response = interrupt(_review_payload(state))
    if not isinstance(response, dict):
        response = {"action": str(response)}
    action = str(response.get("action", "escalate")).lower()
    if action not in VALID_ACTIONS:
        action = "escalate"
    update: dict[str, Any] = {"decision": action}
    if action == "edit":
        text = str(response.get("draft", "")).strip()
        if not text:
            update["decision"] = "escalate"
            update["terminal_reason"] = "Human edit was empty; no draft can be queued."
        else:
            update.update({"human_edit": text, "draft": text})
    elif action == "annotate":
        annotation = str(response.get("annotation", "")).strip()
        critique = dict(state.get("critique", {}))
        annotations = list(critique.get("annotations", []))
        if annotation:
            annotations.append(annotation)
        critique["annotations"] = annotations
        update["critique"] = critique
    elif action == "reject":
        update["terminal_reason"] = "Reviewer rejected the draft."
    elif action == "escalate":
        update["terminal_reason"] = str(response.get("reason") or "Reviewer requested escalation.")
    return update
