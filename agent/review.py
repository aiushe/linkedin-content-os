"""Small, testable controls for resuming a paused human-review run."""

from __future__ import annotations

from typing import Any

STALE_REVIEW_MESSAGE = (
    "This run is no longer paused. No review action was sent; start over to create a new draft."
)


def resume_if_paused(graph: Any, run_config: dict[str, Any], command: Any) -> str | None:
    """Resume only a graph snapshot that still has a pending interrupt."""

    snapshot = graph.get_state(run_config)
    if not snapshot or not snapshot.next:
        return STALE_REVIEW_MESSAGE
    graph.invoke(command, config=run_config)
    return None
