"""Run one traceable, synthetic-corpus case for the Week 4 acceptance gate."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["LANGSMITH_PROJECT"] = "lco-eval-w4"
os.environ["MEM0_ENABLED"] = "false"

@traceable(name="week4-trace-smoke", run_type="chain")
def run_trace(case: dict[str, Any]) -> dict[str, Any]:
    """Trace one real-model run against the tracked synthetic fixture corpus."""

    from agent.graph import build_graph
    from evals.run import run_case

    result = run_case(build_graph(), case)
    current_run = get_current_run_tree()
    if current_run is not None:
        result["trace_url"] = current_run.get_url()
    return result


def main() -> None:
    from evals.metadata import run_config
    from evals.run import configure_fixture_corpus, flush_tracers

    try:
        configure_fixture_corpus()
        case = json.loads((ROOT / "evals" / "golden.jsonl").read_text().splitlines()[0])
        config = run_config(
            {
                "id": case["id"],
                "kind": case["kind"],
                "intent_expected": case.get("forced_intent", "authority"),
            },
            "instrumentation",
        )
        result = run_trace(
            case,
            langsmith_extra={
                "name": config["run_name"],
                "tags": config["tags"],
                "metadata": config["metadata"],
                "project_name": "lco-eval-w4",
            },
        )
        print(json.dumps(result, indent=2))
    finally:
        flush_tracers()


if __name__ == "__main__":
    main()
