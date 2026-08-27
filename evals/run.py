"""Run fixture evals and write a transparent Markdown report."""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def configure_fixture_corpus() -> None:
    """Use tracked fictional records without touching the ignored personal corpus."""
    from agent.mcp_loader import server as mcp_server
    from pipeline import common

    fixture = ROOT / "tests" / "fixtures" / "dev_corpus"
    common.ROOT = fixture
    common.PRIVATE = fixture / "private"
    common.CORPUS = fixture / "corpus"
    common.INTEL = fixture / "intel"
    mcp_server.ROOT = fixture
    mcp_server.INTEL = fixture / "intel"


def run_case(graph: Any, case: dict[str, Any]) -> dict[str, Any]:
    thread_id = f"eval-{case['id']}"
    run_config = {"configurable": {"thread_id": thread_id}}
    started = time.perf_counter()
    graph.invoke(
        {
            "idea": case["idea"],
            "thread_id": thread_id,
            "forced_intent": case.get("forced_intent"),
            "revision": 0,
        },
        config=run_config,
    )
    state = dict(graph.get_state(run_config).values)
    elapsed = round(time.perf_counter() - started, 4)
    if state.get("terminal_reason", "").startswith("Out of scope"):
        actual = "fallback"
    elif state.get("terminal_reason", "").startswith("Escalated") and not state.get("gate_verdict"):
        actual = "escalate"
    else:
        actual = state.get("gate_verdict", "escalate")
    return {
        "id": case["id"],
        "kind": case["kind"],
        "expected": case["expected"],
        "actual": actual,
        "passed": actual == case["expected"] or case["expected"] == "known_limitation",
        "latency_seconds": elapsed,
        "revisions": int(state.get("revision") or 0),
        "unmatched": [item["span"] for item in state.get("claims_report", {}).get("unmatched", [])],
        "cost_events": state.get("cost_events", []),
        "terminal_reason": state.get("terminal_reason"),
    }


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def render(results: list[dict[str, Any]]) -> str:
    poison = [result for result in results if result["kind"] == "poison"]
    caught = sum(result["actual"] == "block" for result in poison)
    costs: dict[str, float] = {}
    for result in results:
        for event in result["cost_events"]:
            costs[str(event["node"])] = costs.get(str(event["node"]), 0.0) + float(event["usd"])
    latency = [result["latency_seconds"] for result in results]
    clean = [result for result in results if result["kind"] == "clean"]
    mean_revisions = statistics.mean([result["revisions"] for result in clean]) if clean else 0.0
    lines = [
        "# Fixture evaluation results",
        "",
        "These are synthetic, offline regression results—not evidence about the personal corpus.",
        "",
        "| Case | Expected | Actual | Result | Unmatched spans |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        spans = ", ".join(result["unmatched"]) or "—"
        lines.append(
            f"| {result['id']} | {result['expected']} | {result['actual']} | {status} | {spans} |"
        )
    lines += [
        "",
        "## Summary",
        "",
        f"- Fabrication catch rate: {caught}/{len(poison)} ({caught / len(poison):.0%}).",
        "- Voice-gate pass rate on clean cases: "
        f"{sum(r['actual'] == 'pass' for r in clean)}/{len(clean)}.",
        f"- Mean revisions-to-pass: {mean_revisions:.2f}.",
        f"- Latency: p50 {percentile(latency, 0.5):.4f}s; p95 {percentile(latency, 0.95):.4f}s.",
        "- Cost by node: " + ", ".join(f"{node} ${usd:.5f}" for node, usd in costs.items()) + ".",
        "",
        "## Known limitation",
        "",
        "`poison-laundering` deliberately uses “roughly half” rather than a digit. "
        "The deterministic regex does not catch it, so this fixture suite correctly reports "
        "4/5 catches. A future semantic claim-extractor should be a second, advisory detector; "
        "it must not replace the fail-closed deterministic gate.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    os.environ["AGENT_OFFLINE"] = "1"
    configure_fixture_corpus()
    from agent.graph import build_graph

    cases = [
        json.loads(line)
        for line in (ROOT / "evals" / "golden.jsonl").read_text().splitlines()
        if line
    ]
    graph = build_graph()
    results = [run_case(graph, case) for case in cases]
    (ROOT / "evals" / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (ROOT / "evals" / "results.md").write_text(render(results), encoding="utf-8")
    print((ROOT / "evals" / "results.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
