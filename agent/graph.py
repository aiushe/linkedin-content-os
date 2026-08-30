"""LangGraph assembly for the collaborative content drafting workflow."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from pipeline.claims import AllowedFact

from .gates import gate as run_gate
from .nodes.commit import commit
from .nodes.critique import critique
from .nodes.ground import ground
from .nodes.hitl import hitl
from .nodes.memory import recall_profile_memory
from .nodes.router import intake_router
from .nodes.write import write
from .state import DraftState


def deterministic_gate(state: DraftState) -> dict:
    """Graph adapter for the pure-Python deterministic gates."""

    allowlist = [AllowedFact(**item) for item in state.get("allowlist", [])]
    report = run_gate(state.get("draft", ""), allowlist, target_format="short_post")
    update = {
        "voice_report": report.voice,
        "claims_report": asdict(report.claims),
        "confidential_report": asdict(report.confidential),
        "gate_verdict": report.verdict,
    }
    return update


def _route_after_router(_: DraftState) -> Literal["ground"]:
    """Every request reaches drafting; the router only supplies a suggested format."""

    return "ground"


def _route_after_ground(_: DraftState) -> Literal["write"]:
    return "write"


def _route_after_write(_: DraftState) -> Literal["gate"]:
    return "gate"


def _route_after_gate(_: DraftState) -> Literal["critique"]:
    """Compute readable observations once, then hand the draft to the user."""

    return "critique"


def _route_after_critique(_: DraftState) -> Literal["hitl"]:
    """Computed critique is a report, not an automatic revision instruction."""

    return "hitl"


def _route_after_hitl(
    state: DraftState,
) -> Literal["commit", "gate", "write", "hitl", "end"]:
    decision = state.get("decision")
    if decision == "approve":
        return "commit"
    if decision == "edit":
        return "gate"
    if decision == "source":
        return "gate"
    if decision == "feedback":
        return "write"
    if decision == "retry":
        return "write"
    if decision == "annotate":
        return "hitl"
    return "end"


def build_graph(*, checkpointer: Any | None = None) -> Any:
    """Build a compiled graph with a memory checkpointer for resumable HITL runs."""

    workflow = StateGraph(DraftState)
    workflow.add_node("profile_memory", recall_profile_memory)
    workflow.add_node("intake_router", intake_router)
    workflow.add_node("ground", ground)
    workflow.add_node("write", write)
    workflow.add_node("gate", deterministic_gate)
    workflow.add_node("critique", critique)
    workflow.add_node("hitl", hitl)
    workflow.add_node("commit", commit)
    workflow.add_edge(START, "profile_memory")
    workflow.add_edge("profile_memory", "intake_router")
    workflow.add_conditional_edges(
        "intake_router",
        _route_after_router,
        {
            "ground": "ground",
        },
    )
    workflow.add_conditional_edges(
        "ground", _route_after_ground, {"write": "write"}
    )
    workflow.add_conditional_edges(
        "write", _route_after_write, {"gate": "gate"}
    )
    workflow.add_conditional_edges(
        "gate",
        _route_after_gate,
        {"critique": "critique"},
    )
    workflow.add_conditional_edges(
        "critique", _route_after_critique, {"hitl": "hitl"}
    )
    workflow.add_conditional_edges(
        "hitl",
        _route_after_hitl,
        {
            "commit": "commit",
            "gate": "gate",
            "write": "write",
            "hitl": "hitl",
            "end": END,
        },
    )
    workflow.add_edge("commit", END)
    return workflow.compile(checkpointer=checkpointer or MemorySaver())
