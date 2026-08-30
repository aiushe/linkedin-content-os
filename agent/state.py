"""State contract and reducers for a single draft run."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, NotRequired, TypedDict

Intent = Literal["authority", "reach", "comment", "profile_rewrite", "outreach", "out_of_scope"]
Decision = Literal[
    "approve",
    "edit",
    "feedback",
    "source",
    "reject",
    "retry",
    "annotate",
]
GateVerdict = Literal["pass", "warn", "revise"]


class DraftState(TypedDict, total=False):
    # Input
    idea: str
    thread_id: str
    forced_intent: NotRequired[Intent | None]

    # Routing
    intent: Intent
    intent_confidence: float
    router_rationale: str

    # Grounding
    stories: list[dict]
    allowlist: list[dict]
    template: dict | None
    grounding_degraded: bool
    degradation_reasons: Annotated[list[str], operator.add]
    market_brief: dict | None
    market_fetched: bool

    # Optional user-approved personal context. It is never part of the factual allowlist.
    profile_memory: list[dict[str, str]]
    profile_memory_status: str

    # Profile-rewrite preflight
    profile_analysis: dict

    # Read-only outreach workflow
    ops_guidance: dict

    # Drafting
    draft: str
    hooks: list[str]
    revision: int
    draft_history: Annotated[list[dict], operator.add]
    user_directions: Annotated[list[str], operator.add]

    # Gates
    voice_report: dict
    claims_report: dict
    confidential_report: dict
    gate_verdict: GateVerdict

    # Critique
    critique: dict

    # Control plane
    errors: Annotated[list[dict], operator.add]
    cost_events: Annotated[list[dict], operator.add]
    decision: Decision | None
    human_edit: str | None
    claim_source_error: str | None
    queue_path: str | None
    terminal_reason: str | None
