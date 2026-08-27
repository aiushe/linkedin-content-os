"""Terminal fallback for requests outside the content-agent remit."""

from __future__ import annotations

from agent.state import DraftState


def fallback(_: DraftState) -> dict:
    return {
        "terminal_reason": (
            "Out of scope: this agent only prepares grounded LinkedIn drafts and comments."
        )
    }
