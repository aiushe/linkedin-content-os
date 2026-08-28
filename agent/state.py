"""State contract and reducers for a single draft run."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, NotRequired, TypedDict

Intent = Literal["authority", "reach", "comment", "out_of_scope"]
Decision = Literal["approve", "edit", "reject", "retry", "escalate", "annotate"]
GateVerdict = Literal["pass", "revise", "block", "indeterminate"]


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

    # Drafting
    draft: str
    hooks: list[str]
    revision: int
    draft_history: Annotated[list[dict], operator.add]

    # Gates
    voice_report: dict
    claims_report: dict
    gate_verdict: GateVerdict

    # Critique
    critique: dict

    # Control plane
    errors: Annotated[list[dict], operator.add]
    cost_events: Annotated[list[dict], operator.add]
    decision: Decision | None
    human_edit: str | None
    queue_path: str | None
    terminal_reason: str | None
