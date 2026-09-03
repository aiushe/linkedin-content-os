"""Turn local-only Week 4 run exports into consistent per-case and aggregate metrics."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from evals import evaluators

ROOT = Path(__file__).resolve().parents[1]


def _results(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = value.get("results")
    return [dict(item) for item in raw] if isinstance(raw, list) else [dict(value)]


def _score(value: Mapping[str, Any], key: str) -> float | None:
    for item in _results(value):
        if item.get("key") == key and isinstance(item.get("score"), (int, float)):
            return float(item["score"])
    return None


def _metadata(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    for item in _results(value):
        if item.get("key") == key:
            metadata = item.get("metadata")
            return dict(metadata) if isinstance(metadata, Mapping) else {}
    return {}


def case_rows(payload: Mapping[str, Any], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate cached target outputs against their immutable source labels."""

    by_case_id = {str(case["id"]): case for case in cases}
    rows: list[dict[str, Any]] = []
    for record in payload.get("records", []):
        if not isinstance(record, Mapping):
            continue
        case = by_case_id.get(str(record.get("case_id")))
        if case is None:
            continue
        run = SimpleNamespace(outputs=dict(record), extra={})
        example = {"inputs": case}
        claims = evaluators.claim_leak(run, example)
        stories = evaluators.story_top1(run, example)
        voice = evaluators.voice_distance(run, example)
        intent = evaluators.intent_completion(run, example)
        efficiency = evaluators.efficiency(run, example)
        observed_stories = [
            str(story.get("id"))
            for story in record.get("stories", [])
            if isinstance(story, Mapping) and story.get("id")
        ]
        expected_stories = [str(item) for item in case.get("expected_story_ids", [])]
        rows.append(
            {
                "case_id": case["id"],
                "kind": case["kind"],
                "intent_expected": case["intent_expected"],
                "intent_predicted": record.get("intent"),
                "expected_story": expected_stories[0] if expected_stories else None,
                "predicted_story": observed_stories[0] if observed_stories else None,
                "story_top1": _score(stories, "story_top1"),
                "story_top3": _score(stories, "story_top3"),
                "claim_leak": _score(claims, "claim_leak"),
                "leak_class": case.get("planted_claim_class"),
                "voice_z": _score(voice, "voice_distance"),
                "intent_completion": _score(intent, "intent_completion"),
                "delivered": _metadata(efficiency, "cost_per_delivered_draft").get("delivered"),
                "latency_s": record.get("latency_seconds"),
                "cost_usd": record.get("cost_usd"),
                "error_classes": ", ".join(
                    record.get("trace_metadata", {}).get("error_classes", [])
                    if isinstance(record.get("trace_metadata"), Mapping)
                    else []
                ),
                "trace_url": record.get("trace_url"),
            }
        )
    return sorted(rows, key=lambda row: str(row["case_id"]))


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _rate(values: list[float]) -> float | None:
    return _mean(values)


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, round((len(ordered) - 1) * 0.95))], 4)


def wilson_interval(successes: int, total: int) -> tuple[float | None, float | None]:
    """Return a 95% Wilson interval for a proportion without an optional dependency."""

    if not total:
        return None, None
    z = 1.96
    rate = successes / total
    denominator = 1 + (z * z / total)
    center = (rate + (z * z / (2 * total))) / denominator
    half = z * math.sqrt((rate * (1 - rate) / total) + (z * z / (4 * total * total)))
    half /= denominator
    return round(center - half, 4), round(center + half, 4)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Produce privacy-safe aggregate metrics from local per-case rows."""

    def numeric(field: str, *, condition: Any = None) -> list[float]:
        return [
            float(row[field])
            for row in rows
            if isinstance(row.get(field), (int, float))
            and (condition is None or condition(row))
        ]

    top1 = numeric("story_top1")
    top1_successes = int(sum(top1))
    top1_ci = wilson_interval(top1_successes, len(top1))
    delivered = [bool(row.get("delivered")) for row in rows]
    error_counts = Counter(
        item.strip()
        for row in rows
        for item in str(row.get("error_classes") or "").split(",")
        if item.strip()
    )
    return {
        "case_count": len(rows),
        "story_top1": _rate(top1),
        "story_top1_n": len(top1),
        "story_top1_ci95": top1_ci,
        "story_top3": _rate(numeric("story_top3")),
        "voice_z_mean": _mean(numeric("voice_z")),
        "intent_completion": _rate(numeric("intent_completion")),
        "delivered": sum(delivered),
        "delivered_rate": sum(delivered) / len(rows) if rows else None,
        "latency_p95_s": _p95(numeric("latency_s")),
        "latency_mean_s": _mean(numeric("latency_s")),
        "cost_mean_usd": _mean(numeric("cost_usd", condition=lambda row: row.get("delivered"))),
        "cost_total_usd": round(sum(numeric("cost_usd")), 6),
        "claim_leak_numeric": _rate(
            numeric("claim_leak", condition=lambda row: row.get("leak_class") == "numeric")
        ),
        "claim_leak_hedged": _rate(
            numeric("claim_leak", condition=lambda row: row.get("leak_class") == "hedged")
        ),
        "error_classes": dict(sorted(error_counts.items())),
    }


def load_rows(
    path: Path, cases_path: Path | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load a local export and its reviewed labels."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    cases_file = cases_path or ROOT / "evals" / "golden_v2.jsonl"
    cases = [
        json.loads(line)
        for line in cases_file.read_text(encoding="utf-8").splitlines()
        if line
    ]
    rows = case_rows(payload, cases)
    return rows, aggregate(rows)
