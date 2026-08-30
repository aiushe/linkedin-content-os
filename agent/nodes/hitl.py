"""Interrupt payload and resume handling for the only write boundary."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from agent.state import DraftState
from pipeline.claims import TruthTableWriteError, append_verified_truth_table_row

VALID_ACTIONS = {"approve", "edit", "feedback", "source", "reject", "retry", "annotate"}


def _available_actions(state: DraftState) -> list[str]:
    """Return every human-review action for the current draft."""

    return sorted(VALID_ACTIONS)


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
        "actions": _available_actions(state),
    }


def _unresolved_spans(state: DraftState) -> list[str]:
    """Return the current flagged spans in their review order."""

    report = state.get("claims_report", {})
    claims = report.get("unresolved", []) if isinstance(report, dict) else []
    spans: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        span = str(claim.get("span") or "").strip()
        if span and span not in spans:
            spans.append(span)
    return spans


def hitl(state: DraftState) -> dict:
    """Pause graph execution and normalize the reviewer's six possible actions."""

    response = interrupt(_review_payload(state))
    if not isinstance(response, dict):
        response = {"action": str(response)}
    action = str(response.get("action", "annotate")).lower()
    if action not in VALID_ACTIONS:
        action = "annotate"
    update: dict[str, Any] = {"decision": action}
    if action == "approve":
        pass
    elif action == "edit":
        text = str(response.get("draft", "")).strip()
        if not text:
            update["decision"] = "annotate"
            update["claim_source_error"] = (
                "Type a complete draft before asking the checks to review it."
            )
        else:
            update.update(
                {
                    "human_edit": text,
                    "draft": text,
                }
            )
    elif action == "feedback":
        feedback = str(response.get("feedback", "")).strip()
        if not feedback:
            update["decision"] = "annotate"
            update["claim_source_error"] = "Tell the writer what you want changed."
        else:
            update.update(
                {
                    "user_directions": [feedback],
                    "revision": int(state.get("revision") or 0) + 1,
                }
            )
    elif action == "source":
        claim = response.get("claim")
        proof = response.get("proof")
        date = response.get("date")
        verified = response.get("verified")
        try:
            added_fact = append_verified_truth_table_row(claim, proof, date, verified)
        except TruthTableWriteError as exc:
            update.update({"decision": "annotate", "claim_source_error": str(exc)})
        else:
            allowlist = list(state.get("allowlist", []))
            allowlist.append(
                {
                    "claim": added_fact.claim,
                    "proof": added_fact.proof,
                    "period": added_fact.period,
                    "source": added_fact.source,
                    "source_ref": added_fact.source_ref,
                }
            )
            update.update(
                {
                    "allowlist": allowlist,
                    "claim_source_error": None,
                }
            )
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
    elif action == "retry":
        update["revision"] = int(state.get("revision") or 0) + 1
    return update
