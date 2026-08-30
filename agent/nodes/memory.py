"""Retrieve approved personal-memory context before the graph routes a request."""

from __future__ import annotations

from agent import config, memory
from agent.errors import AgentFailure, FailureClass
from agent.state import DraftState


def recall_profile_memory(_: DraftState) -> dict:
    """Attach optional context without ever treating it as grounded evidence."""

    if not config.MEM0_ENABLED:
        return {"profile_memory": [], "profile_memory_status": "disabled"}
    if not config.mem0_service_enabled():
        return {"profile_memory": [], "profile_memory_status": "disabled"}
    if not config.mem0_prompt_enabled():
        return {
            "profile_memory": [],
            "profile_memory_status": "withheld_for_langsmith_tracing",
            "degradation_reasons": [
                "Personal memory was withheld because LangSmith tracing has not been approved "
                "for it."
            ],
        }
    try:
        memories = memory.recall_profile_memories()
    except memory.ProfileMemoryError:
        failure = AgentFailure(
            FailureClass.DEGRADABLE,
            "Personal profile memory was unavailable; factual grounding still uses the local "
            "corpus.",
        )
        return {
            "profile_memory": [],
            "profile_memory_status": "unavailable",
            "degradation_reasons": [failure.message],
            "errors": [failure.as_record(node="profile_memory")],
        }
    return {
        "profile_memory": memories,
        "profile_memory_status": "available" if memories else "empty",
    }
