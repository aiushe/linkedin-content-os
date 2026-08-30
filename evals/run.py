"""Measure advisory claim detection and draft delivery with fixture cases."""

from __future__ import annotations

import json
import multiprocessing
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVAL_CASE_TIMEOUT_SECONDS = float(os.getenv("EVAL_CASE_TIMEOUT_SECONDS", "240"))


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


def _detected_plants(unresolved: list[dict[str, Any]], planted: list[str]) -> list[str]:
    observed = {str(item.get("span", "")).lower() for item in unresolved}
    return [claim for claim in planted if claim.lower() in observed]


def case_passed(result: dict[str, Any]) -> bool:
    """A measured case passes only when it is delivered and its expectation holds."""

    if not result["draft_produced"] or not result["reached_user"]:
        return False
    if result["kind"] == "clean":
        return result["clean_unflagged"]
    if result["kind"] == "poison":
        return result["planted_detected"] == result["planted_claims"]
    return True


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
    snapshot = graph.get_state(run_config)
    state = dict(snapshot.values)
    elapsed = round(time.perf_counter() - started, 4)
    claims_report = state.get("claims_report", {})
    unresolved = (
        list(claims_report.get("unresolved", [])) if isinstance(claims_report, dict) else []
    )
    planted = list(case.get("planted_claims", []))
    result = {
        "id": case["id"],
        "kind": case["kind"],
        "planted_claims": planted,
        "planted_detected": _detected_plants(unresolved, planted),
        "unresolved": [item["span"] for item in unresolved],
        "clean_unflagged": not unresolved,
        "draft_produced": bool(state.get("draft")),
        "reached_user": "hitl" in snapshot.next,
        "latency_seconds": elapsed,
        "revisions": int(state.get("revision") or 0),
        "cost_events": state.get("cost_events", []),
        "errors": state.get("errors", []),
        "degradation_reasons": state.get("degradation_reasons", []),
        "note": case.get("note"),
    }
    result["passed"] = case_passed(result)
    return result


def timed_out_result(case: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    """Return a failed delivery result when a live provider run outlasts its deadline."""

    result = {
        "id": case["id"],
        "kind": case["kind"],
        "planted_claims": list(case.get("planted_claims", [])),
        "planted_detected": [],
        "unresolved": [],
        "clean_unflagged": False,
        "draft_produced": False,
        "reached_user": False,
        "latency_seconds": timeout_seconds,
        "revisions": 0,
        "cost_events": [],
        "errors": [
            {
                "node": "eval",
                "class": "capability",
                "message": "Live evaluation case timed out before a draft reached the user.",
                "detail": f"timeout_seconds={timeout_seconds:g}",
            }
        ],
        "degradation_reasons": [],
        "note": case.get("note"),
    }
    result["passed"] = case_passed(result)
    return result


def _live_case_worker(case: dict[str, Any], result_queue: Any) -> None:
    """Build graph state in an isolated process so a stalled provider call is killable."""

    configure_fixture_corpus()
    from agent.graph import build_graph

    result_queue.put(run_case(build_graph(), case))


def run_live_case(case: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    """Run one live case in a process with a parent-enforced deadline."""

    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    process = context.Process(target=_live_case_worker, args=(case, result_queue))
    started = time.perf_counter()
    try:
        process.start()
        process.join(timeout_seconds)
    except KeyboardInterrupt:
        if process.is_alive():
            process.terminate()
            process.join()
        result_queue.close()
        raise
    if process.is_alive():
        process.terminate()
        process.join()
        result_queue.close()
        return timed_out_result(case, round(time.perf_counter() - started, 4))
    try:
        return result_queue.get(timeout=1)
    except Exception:
        result = timed_out_result(case, round(time.perf_counter() - started, 4))
        result["errors"][0]["message"] = "Live evaluation worker exited before a draft result."
        return result
    finally:
        result_queue.close()


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def render(results: list[dict[str, Any]]) -> str:
    measured_poison = [result for result in results if result["kind"] == "poison"]
    true_positives = sum(len(result["planted_detected"]) for result in measured_poison)
    planted_total = sum(len(result["planted_claims"]) for result in measured_poison)
    false_positives = sum(
        len(result["unresolved"]) for result in results if result["kind"] == "clean"
    )
    clean = [result for result in results if result["kind"] == "clean"]
    clean_unflagged = sum(result["clean_unflagged"] for result in clean)
    delivered = sum(result["draft_produced"] and result["reached_user"] for result in results)
    costs: dict[str, float] = {}
    for result in results:
        for event in result["cost_events"]:
            costs[str(event["node"])] = costs.get(str(event["node"]), 0.0) + float(
                event["usd"]
            )
    latency = [result["latency_seconds"] for result in results]
    mean_revisions = (
        statistics.mean([result["revisions"] for result in results]) if results else 0.0
    )
    recall = true_positives / planted_total if planted_total else 1.0
    if true_positives + false_positives:
        precision = true_positives / (true_positives + false_positives)
    else:
        precision = 1.0
    lines = [
        "# Fixture evaluation results",
        "",
        "These use synthetic fixture records, even when live models are enabled; they are not "
        "evidence about the personal corpus.",
        "",
        "| Case | Kind | Planted claims found | Clean draft unflagged | "
        "Draft | Reached user | Result |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        if result["kind"] == "known_limitation":
            status = "KNOWN LIMITATION" if result["passed"] else "FAILED DELIVERY"
        else:
            status = "PASS" if result["passed"] else "FAIL"
        found = ", ".join(result["planted_detected"]) or "—"
        clean_value = "—" if result["kind"] != "clean" else str(result["clean_unflagged"]).lower()
        lines.append(
            f"| {result['id']} | {result['kind']} | {found} | {clean_value} | "
            f"{str(result['draft_produced']).lower()} | {str(result['reached_user']).lower()} | "
            f"{status} |"
        )
    lines += [
        "",
        "## Detection and delivery",
        "",
        f"- Planted-claim recall: {true_positives}/{planted_total} ({recall:.0%}).",
        f"- Claim precision against clean drafts: {precision:.0%} "
        f"({false_positives} false flag(s)).",
        f"- Clean drafts left unflagged: {clean_unflagged}/{len(clean)}.",
        f"- Drafts produced and delivered to the user: {delivered}/{len(results)}.",
        f"- Mean user-requested revisions before review: {mean_revisions:.2f}.",
        f"- Latency: p50 {percentile(latency, 0.5):.4f}s; "
        f"p95 {percentile(latency, 0.95):.4f}s.",
        "- Cost by node: " + ", ".join(f"{node} ${usd:.5f}" for node, usd in costs.items()) + ".",
        "",
    ]
    incidents = [
        f"- `{result['id']}`: {error.get('class')} at {error.get('node')} — "
        f"{error.get('message')}"
        for result in results
        for error in result.get("errors", [])
    ] + [
        f"- `{result['id']}`: context note — {reason}"
        for result in results
        for reason in result.get("degradation_reasons", [])
    ]
    if incidents:
        lines += ["## Context notes", "", *incidents, ""]
    limitations = [result for result in results if result["kind"] == "known_limitation"]
    if limitations:
        lines += ["## Known detector limitations", ""]
        lines += [f"- `{result['id']}`: {result['note']}" for result in limitations]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    os.environ.setdefault("AGENT_OFFLINE", "1")
    configure_fixture_corpus()
    from agent.graph import build_graph

    live = os.environ.get("AGENT_OFFLINE", "1").lower() not in {"1", "true", "yes"}
    cases = [
        json.loads(line)
        for line in (ROOT / "evals" / "golden.jsonl").read_text().splitlines()
        if line
    ]
    graph = build_graph() if not live else None
    mode = "LIVE" if live else "offline"
    print(f"Running {len(cases)} cases ({mode})...", flush=True)
    results = []
    for position, case in enumerate(cases, 1):
        print(f"  [{position}/{len(cases)}] {case['id']} ... ", end="", flush=True)
        result = run_live_case(case, EVAL_CASE_TIMEOUT_SECONDS) if live else run_case(graph, case)
        print(
            f"draft={str(result['draft_produced']).lower()} "
            f"review={str(result['reached_user']).lower()} "
            f"({result['latency_seconds']:.1f}s)",
            flush=True,
        )
        results.append(result)
    print(flush=True)
    (ROOT / "evals" / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (ROOT / "evals" / "results.md").write_text(render(results), encoding="utf-8")
    print((ROOT / "evals" / "results.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
