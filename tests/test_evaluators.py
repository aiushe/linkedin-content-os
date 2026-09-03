"""Unit coverage for the Week 4 evaluator contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from evals import evaluators


def run(outputs: dict) -> SimpleNamespace:
    return SimpleNamespace(
        outputs=outputs,
        extra={},
        start_time=datetime(2026, 9, 2, tzinfo=timezone.utc),
        end_time=datetime(2026, 9, 2, tzinfo=timezone.utc) + timedelta(seconds=12),
    )


def example(**case: object) -> dict:
    return {"inputs": case}


def test_claim_leak_scores_labelled_and_unlabelled_numeric_claims() -> None:
    case = example(planted_claims=["45%"], planted_claim_class="numeric")
    labelled = evaluators.claim_leak(
        run({"draft": "I traced 45% of bugs.", "claims_report": {"unresolved": [{"span": "45%"}]}}),
        case,
    )
    leaked = evaluators.claim_leak(
        run({"draft": "I traced 45% of bugs.", "claims_report": {"unresolved": []}}), case
    )
    assert labelled["score"] == 0.0
    assert leaked["score"] == 1.0
    assert leaked["metadata"]["class"] == "numeric"


def test_story_top1_emits_top3_and_excludes_unlabelled_cases() -> None:
    passed = evaluators.story_top1(
        run({"stories": [{"id": "story-a"}]}), example(expected_story_ids=["story-a"])
    )
    scored = evaluators.story_top1(
        run({"stories": [{"id": "wrong"}, {"id": "story-a"}]}),
        example(expected_story_ids=["story-a"]),
    )
    assert [item["score"] for item in passed["results"]] == [1.0, 1.0]
    assert [item["score"] for item in scored["results"]] == [0.0, 1.0]
    excluded = evaluators.story_top1(run({"stories": []}), example(expected_story_ids=[]))
    assert [item["score"] for item in excluded["results"]] == [None, None]


def test_voice_distance_uses_absolute_z_and_reports_missing_data() -> None:
    passing = evaluators.voice_distance(
        run(
            {
                "voice_report": {
                    "features": {"first_person_rate": 0.15},
                    "scored_features": ["first_person_rate"],
                    "baseline_features": {"first_person_rate": {"mean": 0.1, "stdev": 0.1}},
                }
            }
        ),
        example(),
    )
    failing = evaluators.voice_distance(
        run(
            {
                "voice_report": {
                    "features": {"first_person_rate": 0.3},
                    "scored_features": ["first_person_rate"],
                    "baseline_features": {"first_person_rate": {"mean": 0.1, "stdev": 0.1}},
                }
            }
        ),
        example(),
    )
    missing = evaluators.voice_distance(run({"voice_report": {}}), example())
    assert passing["score"] == 0.5
    assert failing["score"] == 2.0
    assert missing["score"] is None


def test_intent_completion_requires_trajectory_and_graceful_decline() -> None:
    good_path = list(evaluators.STANDARD_DRAFT_PATH)
    case = example(intent_expected="out_of_scope", expected_behavior="graceful_decline")
    passed = evaluators.intent_completion(
        run(
            {
                "intent": "out_of_scope",
                "node_path": good_path,
                "draft": "I can't book travel because I am a LinkedIn content tool.",
            }
        ),
        case,
    )
    failed = evaluators.intent_completion(
        run({"intent": "out_of_scope", "node_path": good_path, "draft": "Book the flight."}),
        case,
    )
    assert passed["score"] == 1.0
    assert failed["score"] == 0.0
    assert failed["metadata"]["graceful_decline"] is False


def test_intent_completion_exposes_unwired_profile_baseline_failure() -> None:
    result = evaluators.intent_completion(
        run({"intent": "profile_rewrite", "node_path": list(evaluators.STANDARD_DRAFT_PATH)}),
        example(intent_expected="profile_rewrite"),
    )
    assert result["score"] == 0.0


def test_efficiency_only_assigns_cost_to_delivered_drafts() -> None:
    delivered = evaluators.efficiency(
        run(
            {
                "draft": "A draft",
                "node_path": list(evaluators.STANDARD_DRAFT_PATH),
                "cost_events": [{"usd": 0.012}],
            }
        ),
        example(),
    )
    undelivered = evaluators.efficiency(run({"cost_events": [{"usd": 0.012}]}), example())
    assert [item["score"] for item in delivered["results"]] == [0.012, 12.0]
    assert undelivered["results"][0]["score"] is None


def test_grounding_faithfulness_requires_calibration_and_records_agreement(monkeypatch) -> None:
    inactive = evaluators.grounding_faithfulness(run({"draft": "A draft"}), example())
    monkeypatch.setattr(
        evaluators,
        "_invoke_grounding_judge",
        lambda _: {"faithful": True, "rationale": "All facts are supported."},
    )
    passing = evaluators.grounding_faithfulness(
        run({"draft": "A draft", "stories": []}),
        example(grounding_calibration=True, grounding_human_label=True, allowed_facts=[]),
    )
    monkeypatch.setattr(
        evaluators,
        "_invoke_grounding_judge",
        lambda _: {"faithful": False, "rationale": "An unsupported fact appeared."},
    )
    failing = evaluators.grounding_faithfulness(
        run({"draft": "A draft", "stories": []}),
        example(grounding_calibration=True, grounding_human_label=True, allowed_facts=[]),
    )
    assert inactive["score"] is None
    assert passing["score"] == 1.0
    assert passing["metadata"]["agreement"] == 1.0
    assert failing["score"] == 0.0
    assert failing["metadata"]["agreement"] == 0.0
