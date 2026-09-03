"""Code and judge-backed evaluators for the Week 4 live evaluation suite.

Every evaluator accepts a LangSmith ``Run`` and ``Example`` (or mapping-shaped test doubles) and
returns a LangSmith-compatible score dictionary.  The JSONL dataset stays the label source of
truth; examples may place its fields in either ``inputs`` or ``outputs``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel

STANDARD_DRAFT_PATH = (
    "profile_memory",
    "intake_router",
    "ground",
    "write",
    "gate",
    "critique",
    "hitl",
)
EXPECTED_NODE_PATHS = {
    "authority": STANDARD_DRAFT_PATH,
    "reach": STANDARD_DRAFT_PATH,
    "comment": STANDARD_DRAFT_PATH,
    "out_of_scope": STANDARD_DRAFT_PATH,
    "profile_rewrite": ("profile_memory", "intake_router", "profile_rewrite"),
    "outreach": ("profile_memory", "intake_router", "outreach"),
}
DECLINE_TERMS = ("cannot", "can't", "can’t", "unable", "not able", "won't", "won’t")


def _mapping(value: Any) -> dict[str, Any]:
    """Coerce a LangSmith object or a test double into a plain mapping."""

    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {
        name: getattr(value, name)
        for name in ("inputs", "outputs", "extra", "start_time", "end_time")
        if hasattr(value, name)
    }


def _value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _case(example: Any) -> dict[str, Any]:
    """Read a case whether the dataset stores labels as inputs or reference outputs."""

    inputs = _mapping(_value(example, "inputs", {}))
    outputs = _mapping(_value(example, "outputs", {}))
    case = {**inputs, **outputs}
    nested = case.get("case")
    return {**case, **_mapping(nested)} if nested else case


def _outputs(run: Any) -> dict[str, Any]:
    return _mapping(_value(run, "outputs", {}))


def _normalise(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def _spans(report: Any) -> set[str]:
    unresolved = _mapping(report).get("unresolved", [])
    spans: set[str] = set()
    for item in unresolved if isinstance(unresolved, list) else []:
        span = _mapping(item).get("span") if isinstance(item, Mapping) else item
        normalised = _normalise(span)
        if normalised:
            spans.add(normalised)
    return spans


def _matches_span(claim: str, spans: set[str]) -> bool:
    normalised = _normalise(claim)
    return any(normalised in span or span in normalised for span in spans)


def claim_leak(run: Any, example: Any) -> dict[str, Any]:
    """Score labelled planted claims that reach a final draft without a gate label."""

    case = _case(example)
    outputs = _outputs(run)
    draft = _normalise(outputs.get("draft"))
    planted = [str(claim) for claim in case.get("planted_claims", [])]
    present = [claim for claim in planted if _normalise(claim) in draft]
    spans = _spans(outputs.get("claims_report", {}))
    leaks = [claim for claim in present if not _matches_span(claim, spans)]
    claim_class = case.get("planted_claim_class")
    total = len(present)
    rate = len(leaks) / total if total else 0.0
    return {
        "key": "claim_leak",
        "score": rate,
        "metadata": {
            "class": claim_class,
            "present_claims": present,
            "unlabelled_claims": leaks,
            "denominator": total,
        },
        "comment": f"{len(leaks)}/{total} labelled planted claim(s) leaked unlabelled.",
    }


def story_top1(run: Any, example: Any) -> dict[str, Any]:
    """Score exact top-1 story retrieval and emit top-3 recall as a companion metric."""

    expected = [str(item) for item in _case(example).get("expected_story_ids", [])]
    if not expected:
        return {
            "results": [
                {
                    "key": "story_top1",
                    "score": None,
                    "value": "not_applicable",
                    "metadata": {"denominator": 0},
                    "comment": "No expected story label; excluded from story retrieval metrics.",
                },
                {
                    "key": "story_top3",
                    "score": None,
                    "value": "not_applicable",
                    "metadata": {"denominator": 0},
                    "comment": "No expected story label; excluded from story retrieval metrics.",
                },
            ]
        }
    stories = _outputs(run).get("stories", [])
    observed = [
        str(_mapping(story).get("id"))
        for story in stories
        if _mapping(story).get("id")
    ]
    return {
        "results": [
            {
                "key": "story_top1",
                "score": float(bool(observed and observed[0] == expected[0])),
                "metadata": {"expected": expected[0], "observed": observed[:1], "denominator": 1},
            },
            {
                "key": "story_top3",
                "score": float(expected[0] in observed[:3]),
                "metadata": {"expected": expected[0], "observed": observed[:3], "denominator": 1},
            },
        ]
    }


def _voice_baseline(report: Mapping[str, Any]) -> dict[str, Any]:
    """Use an embedded test baseline when available, otherwise the local fingerprint."""

    embedded = _mapping(report.get("baseline_features"))
    if embedded:
        return embedded
    from pipeline.voice import load_fingerprint

    return _mapping(load_fingerprint().get("features", {}))


def voice_distance(run: Any, example: Any) -> dict[str, Any]:
    """Return mean absolute z across the report's scored voice features."""

    del example
    report = _mapping(_outputs(run).get("voice_report", {}))
    features = _mapping(report.get("features"))
    scored = [str(name) for name in report.get("scored_features", [])]
    if not scored:
        return {
            "key": "voice_distance",
            "score": None,
            "value": "not_measurable",
            "metadata": {"scored_features": scored},
            "comment": "No scored voice features with a non-zero fingerprint standard deviation.",
        }
    baseline = _voice_baseline(report)
    distances: list[float] = []
    for name in scored:
        expected = _mapping(baseline.get(name))
        stdev = expected.get("stdev")
        actual = features.get(name)
        mean = expected.get("mean")
        if not isinstance(actual, (int, float)) or not isinstance(mean, (int, float)):
            continue
        if not isinstance(stdev, (int, float)) or stdev == 0:
            continue
        distances.append(abs(float(actual) - float(mean)) / abs(float(stdev)))
    if not distances:
        return {
            "key": "voice_distance",
            "score": None,
            "value": "not_measurable",
            "metadata": {"scored_features": scored},
            "comment": "No scored voice features with a non-zero fingerprint standard deviation.",
        }
    return {
        "key": "voice_distance",
        "score": round(sum(distances) / len(distances), 8),
        "metadata": {"scored_features": scored, "feature_z": distances},
    }


def _ordered_path(outputs: Mapping[str, Any]) -> tuple[str, ...]:
    path = outputs.get("node_path", outputs.get("trajectory", []))
    if not isinstance(path, Sequence) or isinstance(path, str):
        return ()
    return tuple(str(node) for node in path)


def _is_graceful_decline(draft: str) -> bool:
    text = _normalise(draft)
    return "linkedin content tool" in text and any(term in text for term in DECLINE_TERMS)


def intent_completion(run: Any, example: Any) -> dict[str, Any]:
    """Score intent-specific graph trajectory, including out-of-scope draft behaviour."""

    case = _case(example)
    outputs = _outputs(run)
    expected_intent = str(case.get("intent_expected", ""))
    expected_path = EXPECTED_NODE_PATHS.get(expected_intent, ())
    observed_path = _ordered_path(outputs)
    observed_intent = outputs.get("intent")
    path_matches = bool(expected_path) and observed_path == expected_path
    intent_matches = observed_intent == expected_intent
    graceful_decline = True
    if case.get("expected_behavior") == "graceful_decline":
        graceful_decline = (
            _is_graceful_decline(str(outputs.get("draft") or ""))
            and "hitl" in observed_path
        )
    passed = path_matches and intent_matches and graceful_decline
    return {
        "key": "intent_completion",
        "score": float(passed),
        "metadata": {
            "expected_intent": expected_intent,
            "observed_intent": observed_intent,
            "expected_path": list(expected_path),
            "observed_path": list(observed_path),
            "expected_behavior": case.get("expected_behavior"),
            "graceful_decline": graceful_decline,
        },
        "comment": (
            "Trajectory and requested behavior matched."
            if passed
            else "Trajectory or requested behavior did not match."
        ),
    }


def _cost_usd(outputs: Mapping[str, Any], run: Any) -> float:
    direct = outputs.get("cost_usd")
    if isinstance(direct, (int, float)):
        return float(direct)
    events = outputs.get("cost_events", [])
    if isinstance(events, list):
        return sum(
            float(_mapping(event).get("usd") or 0)
            for event in events
            if isinstance(_mapping(event).get("usd"), (int, float))
        )
    metadata = _mapping(_mapping(_value(run, "extra", {})).get("metadata"))
    return float(metadata.get("total_cost") or 0.0)


def _latency_seconds(outputs: Mapping[str, Any], run: Any) -> float | None:
    direct = outputs.get("latency_seconds")
    if isinstance(direct, (int, float)):
        return float(direct)
    started = _value(run, "start_time")
    ended = _value(run, "end_time")
    if isinstance(started, datetime) and isinstance(ended, datetime):
        return (ended - started).total_seconds()
    return None


def efficiency(run: Any, example: Any) -> dict[str, Any]:
    """Emit delivered-draft cost and latency without charging failed deliveries as successes."""

    del example
    outputs = _outputs(run)
    delivered = bool(outputs.get("draft")) and "hitl" in _ordered_path(outputs)
    cost = _cost_usd(outputs, run)
    latency = _latency_seconds(outputs, run)
    return {
        "results": [
            {
                "key": "cost_per_delivered_draft",
                "score": cost if delivered else None,
                "value": "delivered" if delivered else "not_delivered",
                "metadata": {"delivered": delivered, "cost_usd": cost},
            },
            {
                "key": "latency_seconds",
                "score": latency,
                "metadata": {"delivered": delivered},
            },
        ]
    }


def _human_label_score(value: Any) -> float | None:
    if value is True or str(value).lower() in {"pass", "faithful", "grounded", "true"}:
        return 1.0
    if value is False or str(value).lower() in {"fail", "unfaithful", "ungrounded", "false"}:
        return 0.0
    return None


class GroundingJudgment(BaseModel):
    """Structured response contract for the calibration-only grounding judge."""

    faithful: bool
    rationale: str


def _invoke_grounding_judge(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Call the configured critic only after a human-labelled calibration case is supplied."""

    from agent.models import get_model

    prompt = (
        "Judge grounding faithfulness. Return JSON with boolean `faithful` and short `rationale`. "
        "A draft is faithful only when each factual statement is supported by retrieved stories "
        "or allowed facts.\n\n"
        f"Draft:\n{payload['draft']}\n\nRetrieved stories:\n{payload['stories']}\n\n"
        f"Allowed facts:\n{payload['allowed_facts']}"
    )
    response = get_model("critic").with_structured_output(GroundingJudgment).invoke(prompt)
    return response.model_dump()


def grounding_faithfulness(run: Any, example: Any) -> dict[str, Any]:
    """Run a calibrated LLM judge only on human-labelled calibration examples.

    A case must carry both ``grounding_calibration: true`` and a human-entered
    ``grounding_human_label``.  This prevents uncalibrated judge feedback from being reported as
    a metric and keeps the evaluator inactive until the required 15 labels exist.
    """

    case = _case(example)
    human_score = _human_label_score(case.get("grounding_human_label"))
    if not case.get("grounding_calibration") or human_score is None:
        return {
            "key": "grounding_faithfulness",
            "score": None,
            "value": "not_calibrated",
            "comment": "Requires a human-labelled calibration example before an LLM judge runs.",
        }
    outputs = _outputs(run)
    judgment = _mapping(
        _invoke_grounding_judge(
            {
                "draft": outputs.get("draft", ""),
                "stories": outputs.get("stories", []),
                "allowed_facts": case.get("allowed_facts", []),
            }
        )
    )
    judge_score = _human_label_score(judgment.get("faithful"))
    if judge_score is None:
        raise ValueError("Grounding judge response must include a boolean `faithful` field.")
    return {
        "key": "grounding_faithfulness",
        "score": judge_score,
        "metadata": {
            "human_score": human_score,
            "agreement": float(judge_score == human_score),
            "rationale": judgment.get("rationale", ""),
        },
    }


EVALUATORS: tuple[Callable[[Any, Any], dict[str, Any]], ...] = (
    claim_leak,
    story_top1,
    voice_distance,
    intent_completion,
    efficiency,
    grounding_faithfulness,
)
