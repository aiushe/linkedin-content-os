"""Run the fixed Week 4 dataset as a private LangSmith evaluation experiment.

The offline gate in :mod:`evals.run` remains intentionally separate.  This runner
executes the real graph, uploads the fixed reviewer dataset only once, and writes
per-case outputs to gitignored local files for the spreadsheet and notebook.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

# These settings must exist before importing agent.config, which reads the environment once.
os.environ["LANGSMITH_PROJECT"] = "lco-eval-w4"
os.environ["MEM0_ENABLED"] = "false"
os.environ["CONFIDENTIAL_TERMS_ENABLED"] = "false"

from langsmith import Client, traceable
from langsmith.run_helpers import get_current_run_tree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET_NAME = "lco-golden"
DATASET_VERSION = "v1"
PROJECT_PREFIX = "lco-eval-w4"
RESULTS_DIR = ROOT / "evals" / "results"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def dataset_cases(corpus: str) -> list[dict[str, Any]]:
    """Return the real reviewer dataset or the safe fixture-only smoke dataset."""

    name = "golden_v2.jsonl" if corpus == "real" else "golden.jsonl"
    return _load_jsonl(ROOT / "evals" / name)


def dataset_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    nested = value.get("case")
    if isinstance(nested, Mapping):
        return dict(nested)
    return dict(value)


def _dataset_metadata(cases: list[dict[str, Any]], source_sha: str) -> dict[str, Any]:
    return {
        "dataset_version": DATASET_VERSION,
        "source_sha256": source_sha,
        "case_count": len(cases),
        "privacy": "private-reviewer-data; no public sharing",
    }


def _tag_dataset_v1(client: Client, dataset: Any) -> None:
    """Apply the v1 tag to the newest committed version without timestamp races."""

    version = next(client.list_dataset_versions(dataset_id=dataset.id, limit=1), None)
    if version is None:
        raise RuntimeError("LangSmith has not exposed a dataset version to tag yet.")
    client.update_dataset_tag(dataset_id=dataset.id, as_of=version.as_of, tag=DATASET_VERSION)


def upload_dataset(client: Client, *, corpus: str = "real") -> Any:
    """Create the immutable private dataset, or verify its exact existing version.

    A dataset is never replaced in place.  A differing SHA is a hard error because
    changing labels after a baseline would invalidate every reported delta.
    """

    if corpus != "real":
        raise ValueError("Only the reviewed real dataset may be uploaded as lco-golden.")
    path = ROOT / "evals" / "golden_v2.jsonl"
    cases = dataset_cases(corpus)
    source_sha = dataset_sha256(path)
    metadata = _dataset_metadata(cases, source_sha)
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        existing = getattr(dataset, "metadata", {}) or {}
        if existing.get("source_sha256") != source_sha:
            raise RuntimeError(
                "Existing lco-golden does not match the fixed v1 dataset SHA; "
                "refusing to mutate it."
            )
        if existing.get("case_count") != len(cases):
            raise RuntimeError("Existing lco-golden case count differs; refusing to mutate it.")
        _tag_dataset_v1(client, dataset)
        return dataset

    dataset = client.create_dataset(
        DATASET_NAME,
        description="Private Week 4 reviewer dataset. Never create a public share link.",
        metadata=metadata,
    )
    for case in cases:
        client.create_example(
            dataset_id=dataset.id,
            inputs=case,
            outputs={"case_id": case["id"]},
            metadata={"dataset_version": DATASET_VERSION, "case_id": case["id"]},
        )
    _tag_dataset_v1(client, dataset)
    return client.read_dataset(dataset_id=dataset.id)


def _node_path(graph: Any, payload: dict[str, Any], config: dict[str, Any]) -> list[str]:
    """Run the graph once and retain its observed trajectory up to the HITL interrupt."""

    node_path: list[str] = []
    for update in graph.stream(payload, config=config, stream_mode="updates"):
        if not isinstance(update, Mapping):
            continue
        for node in update:
            if node != "__interrupt__":
                node_path.append(str(node))
    return node_path


def _cost_usd(events: Any) -> float:
    return round(
        sum(
            float(event.get("usd") or 0.0)
            for event in events if isinstance(event, Mapping)
        )
        if isinstance(events, list)
        else 0.0,
        8,
    )


@traceable(name="week4-live-case", run_type="chain")
def _run_target(case_input: Mapping[str, Any], run_group: str) -> dict[str, Any]:
    """Invoke one graph case and expose the complete evaluator contract."""

    from agent.graph import build_graph
    from evals.metadata import attach_outcome_metadata, run_config

    case = _case_payload(case_input)
    config = run_config(case, run_group)
    graph = build_graph()
    started = time.perf_counter()
    node_path = _node_path(
        graph,
        {
            "idea": case["idea"],
            "thread_id": config["configurable"]["thread_id"],
            "forced_intent": case.get("forced_intent"),
            "revision": 0,
        },
        config,
    )
    snapshot = graph.get_state(config)
    if "hitl" in snapshot.next and (not node_path or node_path[-1] != "hitl"):
        node_path.append("hitl")
    state = dict(snapshot.values)
    latency = round(time.perf_counter() - started, 4)
    outcome = attach_outcome_metadata(state)
    current_run = get_current_run_tree()
    return {
        "case_id": case["id"],
        "kind": case["kind"],
        "intent": state.get("intent"),
        "draft": state.get("draft", ""),
        "stories": state.get("stories", []),
        "claims_report": state.get("claims_report", {}),
        "voice_report": state.get("voice_report", {}),
        "next": list(snapshot.next),
        "node_path": node_path,
        "latency_seconds": latency,
        "cost_events": state.get("cost_events", []),
        "cost_usd": _cost_usd(state.get("cost_events", [])),
        "errors": state.get("errors", []),
        "degradation_reasons": state.get("degradation_reasons", []),
        "trace_metadata": outcome,
        "trace_url": current_run.get_url() if current_run is not None else None,
    }


def make_target(run_group: str):
    """Create a LangSmith target with per-case names, tags, and stable metadata."""

    def target(inputs: dict[str, Any]) -> dict[str, Any]:
        from evals.metadata import run_config

        case = _case_payload(inputs)
        config = run_config(case, run_group)
        return _run_target(
            case,
            run_group,
            langsmith_extra={
                "name": config["run_name"],
                "tags": config["tags"],
                "metadata": config["metadata"],
                "project_name": PROJECT_PREFIX,
            },
        )

    return target


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _experiment_records(results: Iterable[Any]) -> list[dict[str, Any]]:
    """Extract serialisable local rows without relying on a LangSmith result class shape."""

    records: list[dict[str, Any]] = []
    for item in results:
        row = _mapping(item)
        run = _mapping(row.get("run"))
        output = _mapping(run.get("outputs"))
        if not output:
            output = _mapping(row.get("output"))
        if not output:
            continue
        output["trace_url"] = output.get("trace_url") or run.get("url")
        output["evaluation_results"] = _mapping(row.get("evaluation_results"))
        records.append(output)
    return records


def _estimate_cost(cases: list[dict[str, Any]]) -> str:
    pilot_path = RESULTS_DIR / "pilot_real.json"
    if not pilot_path.exists():
        return "unpriced until the five-case pilot provides a measured local rate"
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    costs = [float(row.get("cost_usd") or 0.0) for row in pilot.get("records", [])]
    if not costs or not any(costs):
        return "unpriced because the configured models have no local price table"
    return f"${statistics.mean(costs) * len(cases):.4f} from the pilot mean"


def _result_path(run_group: str, corpus: str) -> Path:
    safe_group = run_group.replace("/", "-")
    return RESULTS_DIR / f"{safe_group}_{corpus}.json"


def export_experiment(
    experiment_name: str, *, run_group: str, corpus: str = "real"
) -> dict[str, Any]:
    """Recover completed experiment outputs into the local-only results cache.

    LangSmith evaluation workers can outlive a terminal session.  This recovery path is
    deliberately read-only against LangSmith: it exports the completed target outputs rather
    than rerunning, replacing, or otherwise changing the fixed dataset or experiment.
    """

    from evals.metadata import git_sha

    client = Client()
    project = client.read_project(project_name=experiment_name)
    records: list[dict[str, Any]] = []
    for run in client.list_runs(project_name=experiment_name, is_root=True, limit=100):
        output = _mapping(getattr(run, "outputs", {}))
        if not output.get("case_id"):
            continue
        output["trace_url"] = output.get("trace_url") or getattr(run, "url", None)
        records.append(output)
    records.sort(key=lambda record: str(record["case_id"]))
    payload = {
        "run_group": run_group,
        "corpus": corpus,
        "dataset_name": DATASET_NAME if corpus == "real" else None,
        "dataset_url": None,
        "dataset_sha256": dataset_sha256(ROOT / "evals" / "golden_v2.jsonl")
        if corpus == "real"
        else None,
        "experiment_name": experiment_name,
        "project_url": getattr(project, "url", None),
        "agent_sha": git_sha(),
        "records": records,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _result_path(run_group, corpus)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Exported {len(records)} completed case(s) to {path.relative_to(ROOT)}.")
    return payload


def run_evaluation(
    *, run_group: str, limit: int | None = None, corpus: str = "real", max_concurrency: int = 4
) -> dict[str, Any]:
    """Run one private experiment and save its per-case results locally only."""

    from evals.evaluators import EVALUATORS
    from evals.metadata import git_sha
    from evals.run import configure_fixture_corpus, flush_tracers

    if corpus == "fixture":
        configure_fixture_corpus()
    client = Client()
    if corpus == "real":
        dataset = upload_dataset(client)
        data: Any = DATASET_NAME
    else:
        dataset = None
        data = dataset_cases("fixture")
    selected = dataset_cases(corpus)[:limit] if limit else dataset_cases(corpus)
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be at least one.")
        if isinstance(data, str):
            by_case_id = {
                str(example.inputs.get("id")): example
                for example in client.list_examples(dataset_name=data, limit=100)
            }
            data = [by_case_id[case["id"]] for case in selected]
        else:
            data = list(data)[:limit]
    print(f"Estimated cost before start: {_estimate_cost(selected)}.", flush=True)
    experiment_prefix = f"{PROJECT_PREFIX}-{run_group}"
    metadata = {
        "dataset_version": DATASET_VERSION if corpus == "real" else "fixture",
        "run_group": run_group,
        "corpus": corpus,
        "agent_sha": git_sha(),
        "privacy": "private real-corpus traces; fixture traces only may be shared",
        "metadata_schema": "week4-v1",
    }
    try:
        results = client.evaluate(
            make_target(run_group),
            data=data,
            evaluators=list(EVALUATORS),
            max_concurrency=max_concurrency,
            metadata=metadata,
            experiment_prefix=experiment_prefix,
            description=(
                "Week 4 fixed-dataset live evaluation. Real-corpus traces remain private."
                if corpus == "real"
                else "Week 4 fixture-only trace evidence; no personal corpus."
            ),
            blocking=True,
        )
        records = _experiment_records(results)
        experiment_name = getattr(results, "experiment_name", None)
        project_url = None
        if experiment_name:
            project = client.read_project(project_name=experiment_name)
            project_url = getattr(project, "url", None)
    finally:
        flush_tracers()
    payload = {
        "run_group": run_group,
        "corpus": corpus,
        "dataset_name": DATASET_NAME if dataset is not None else None,
        "dataset_url": getattr(dataset, "url", None) if dataset is not None else None,
        "dataset_sha256": dataset_sha256(ROOT / "evals" / "golden_v2.jsonl")
        if corpus == "real"
        else None,
        "experiment_name": experiment_name,
        "project_url": project_url,
        "records": records,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _result_path(run_group, corpus)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    actual_cost = sum(float(record.get("cost_usd") or 0.0) for record in records)
    print(
        f"Completed {len(records)} case(s); actual locally priced cost: ${actual_cost:.4f}.",
        flush=True,
    )
    print(f"Experiment: {project_url or experiment_name or 'unavailable'}", flush=True)
    print(f"Local private results: {path.relative_to(ROOT)}", flush=True)
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-group",
        required=True,
        choices=("baseline", "pilot", "improved-1", "improved-2", "improved-3", "improved-4"),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--corpus", choices=("real", "fixture"), default="real")
    parser.add_argument("--max-concurrency", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_evaluation(
        run_group=args.run_group,
        limit=args.limit,
        corpus=args.corpus,
        max_concurrency=args.max_concurrency,
    )


if __name__ == "__main__":
    main()
