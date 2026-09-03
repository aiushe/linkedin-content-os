"""Shared LangSmith metadata for reproducible Week 4 evaluation runs."""

from __future__ import annotations

import subprocess
from typing import Any, Mapping

from agent import config
from agent.nodes.critique import CRITIQUE_PROMPT_VERSION
from agent.nodes.router import ROUTER_PROMPT_VERSION
from agent.nodes.write import WRITE_PROMPT_VERSION


def git_sha() -> str:
    """Return the repository revision, or a visible fallback outside a git checkout."""

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_config(
    case: Mapping[str, Any], run_group: str, *, offline: bool = False
) -> dict[str, Any]:
    """Return the stable config schema shared by every Week 4 evaluation run."""

    return {
        "configurable": {"thread_id": f"eval-{case['id']}"},
        "run_name": f"case:{case['id']}",
        "tags": [str(case["kind"]), str(case["intent_expected"]), run_group],
        "metadata": {
            "case_id": case["id"],
            "kind": case["kind"],
            "intent_expected": case["intent_expected"],
            "prompt_version": WRITE_PROMPT_VERSION,
            "router_prompt_version": ROUTER_PROMPT_VERSION,
            "critique_prompt_version": CRITIQUE_PROMPT_VERSION,
            "agent_sha": git_sha(),
            "dataset_version": "v1",
            "run_group": run_group,
            "writer_model": config.MODEL_WRITER,
            "router_model": config.MODEL_ROUTER,
            "offline": offline,
        },
    }


def outcome_metadata(state: Mapping[str, Any]) -> dict[str, Any]:
    """Normalise error and degradation state for trace metadata."""

    errors = [item for item in state.get("errors", []) if isinstance(item, Mapping)]
    return {
        "error_classes": sorted(
            {str(item["class"]) for item in errors if item.get("class")}
        ),
        "error_nodes": sorted({str(item["node"]) for item in errors if item.get("node")}),
        "degradation_reasons": [
            str(reason) for reason in state.get("degradation_reasons", [])
        ],
    }


def attach_outcome_metadata(state: Mapping[str, Any]) -> dict[str, Any]:
    """Attach case-outcome metadata when execution is inside a LangSmith parent run."""

    metadata = outcome_metadata(state)
    from langsmith.run_helpers import get_current_run_tree

    current_run = get_current_run_tree()
    if current_run is not None:
        current_run.add_metadata(metadata)
    return metadata
