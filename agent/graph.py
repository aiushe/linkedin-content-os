"""LangGraph assembly for the human-gated content drafting workflow."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from pipeline.claims import AllowedFact

from . import config
from .gates import gate as run_gate
from .nodes.commit import commit
from .nodes.critique import critique
from .nodes.escalate import escalate
from .nodes.fallback import fallback
from .nodes.ground import ground
from .nodes.hitl import hitl
from .nodes.router import intake_router
from .nodes.write import write
from .state import DraftState


def deterministic_gate(state: DraftState) -> dict:
    """Graph adapter for the pure-Python dual gate."""

    allowlist = [AllowedFact(**item) for item in state.get("allowlist", [])]
    report = run_gate(state.get("draft", ""), allowlist)
    update = {
        "voice_report": report.voice,
        "claims_report": asdict(report.claims),
        "gate_verdict": report.verdict,
    }
    if report.verdict == "block":
        spans = [claim.span for claim in report.claims.unmatched]
        update["errors"] = [
            {
                "node": "gate",
                "class": "integrity",
                "message": "Draft contains a factual claim that cannot be grounded.",
                "detail": ", ".join(spans),
            }
        ]
    elif report.verdict == "indeterminate":
        update["errors"] = [
            {
                "node": "gate",
                "class": "capability",
                "message": "The gate lacks a viable voice fingerprint or factual allowlist.",
                "detail": "Human corpus seeding is required before safe drafting.",
            }
        ]
    return update


def _route_after_router(state: DraftState) -> Literal["ground", "fallback", "escalate"]:
    if float(state.get("intent_confidence") or 0) < config.ROUTER_CONFIDENCE_FLOOR:
        return "escalate"
    if state.get("intent") == "out_of_scope":
        return "fallback"
    return "ground"


def _route_after_ground(state: DraftState) -> Literal["write", "escalate"]:
    if any(error.get("class") == "capability" for error in state.get("errors", [])):
        return "escalate"
    return "write"


def _route_after_write(state: DraftState) -> Literal["gate", "escalate"]:
    """A writer-model outage must escalate, never flow a placeholder into the gate."""

    for error in state.get("errors", []):
        if error.get("node") == "write" and error.get("class") == "capability":
            return "escalate"
    return "gate"


def _route_after_gate(state: DraftState) -> Literal["hitl", "critique", "escalate"]:
    if state.get("gate_verdict") == "pass":
        return "hitl"
    if state.get("gate_verdict") == "revise":
        return "critique"
    return "escalate"


def _route_after_critique(state: DraftState) -> Literal["write", "escalate"]:
    return "escalate" if int(state.get("revision") or 0) > config.MAX_REVISIONS else "write"


def _route_after_hitl(
    state: DraftState,
) -> Literal["commit", "gate", "write", "escalate", "hitl", "end"]:
    decision = state.get("decision")
    if decision == "approve":
        return "commit"
    if decision == "edit":
        return "gate"
    if decision == "retry":
        return "write"
    if decision == "escalate":
        return "escalate"
    if decision == "annotate":
        return "hitl"
    return "end"


def build_graph(*, checkpointer: Any | None = None) -> Any:
    """Build a compiled graph with a memory checkpointer for resumable HITL runs."""

    workflow = StateGraph(DraftState)
    workflow.add_node("intake_router", intake_router)
    workflow.add_node("ground", ground)
    workflow.add_node("write", write)
    workflow.add_node("gate", deterministic_gate)
    workflow.add_node("critique", critique)
    workflow.add_node("hitl", hitl)
    workflow.add_node("commit", commit)
    workflow.add_node("fallback", fallback)
    workflow.add_node("escalate", escalate)
    workflow.add_edge(START, "intake_router")
    workflow.add_conditional_edges(
        "intake_router",
        _route_after_router,
        {"ground": "ground", "fallback": "fallback", "escalate": "escalate"},
    )
    workflow.add_conditional_edges(
        "ground", _route_after_ground, {"write": "write", "escalate": "escalate"}
    )
    workflow.add_conditional_edges(
        "write", _route_after_write, {"gate": "gate", "escalate": "escalate"}
    )
    workflow.add_conditional_edges(
        "gate",
        _route_after_gate,
        {"hitl": "hitl", "critique": "critique", "escalate": "escalate"},
    )
    workflow.add_conditional_edges(
        "critique", _route_after_critique, {"write": "write", "escalate": "escalate"}
    )
    workflow.add_conditional_edges(
        "hitl",
        _route_after_hitl,
        {
            "commit": "commit",
            "gate": "gate",
            "write": "write",
            "escalate": "escalate",
            "hitl": "hitl",
            "end": END,
        },
    )
    workflow.add_edge("commit", END)
    workflow.add_edge("fallback", END)
    workflow.add_edge("escalate", END)
    return workflow.compile(checkpointer=checkpointer or MemorySaver())
