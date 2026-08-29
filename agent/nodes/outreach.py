"""Read-only, human-operated outreach workflow.

The target-mapper and comment-drafter skills explicitly forbid automating people searches,
connection requests, messages, and follow-ups. This node only points a reviewer at the existing
manual queues and never writes account or person information.
"""

from __future__ import annotations

from agent.state import DraftState
from pipeline import common

OUTREACH_LOG = "ops/outreach-log.md"
ENGAGEMENT_QUEUE = "ops/engagement-queue.md"


def _has_applied(idea: str) -> bool:
    text = idea.lower()
    return "applied" in text or "application submitted" in text


def outreach(state: DraftState) -> dict:
    """Return manual next steps only after the user says they have applied."""

    available = {
        "outreach_log": (common.ROOT / OUTREACH_LOG).is_file(),
        "engagement_queue": (common.ROOT / ENGAGEMENT_QUEUE).is_file(),
    }
    guidance = {
        "manual_only": True,
        "surfaces": {
            name: path
            for name, path in (
                ("outreach_log", OUTREACH_LOG),
                ("engagement_queue", ENGAGEMENT_QUEUE),
            )
            if available[name]
        },
        "sequence": [
            "Open the relevant company page manually.",
            "Use People, then the target function and location filters.",
            "If results are thin, remove location and keep the team keyword.",
            "Paste likely people for human review before drafting any comment.",
        ],
    }
    if not _has_applied(state.get("idea", "")):
        return {
            "ops_guidance": guidance,
            "errors": [
                {
                    "node": "outreach",
                    "class": "sequence",
                    "message": "Outreach halted: apply before target mapping or engagement.",
                    "detail": "The application-first rule prevents relationship theater.",
                }
            ],
            "terminal_reason": (
                "Outreach stopped: apply first, then return for manual target mapping."
            ),
        }
    return {
        "ops_guidance": guidance,
        "terminal_reason": (
            "Outreach is manual: review the target map, then add human-approved activity to the "
            "outreach log or engagement queue yourself."
        ),
    }
