"""Terminal escalation for unsafe, unavailable, or ambiguous paths."""

from __future__ import annotations

from agent import config
from agent.state import DraftState


def escalate(state: DraftState) -> dict:
    reason = state.get("terminal_reason")
    if not reason:
        verdict = state.get("gate_verdict")
        if verdict == "block":
            reason = "Integrity stop: the draft contains an ungrounded factual claim."
        elif verdict == "indeterminate":
            reason = "Escalated: the voice or claims gate cannot verify this draft safely."
        elif int(state.get("revision") or 0) > config.MAX_REVISIONS:
            reason = "Escalated: revision cap reached with the full draft history retained."
        else:
            reason = "Escalated for human review."
    return {"terminal_reason": reason}
