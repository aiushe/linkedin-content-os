from __future__ import annotations

from evals.results_summary import aggregate, case_rows, wilson_interval


def test_summary_rows_and_aggregates_are_label_driven() -> None:
    cases = [
        {
            "id": "case-1",
            "kind": "happy",
            "intent_expected": "authority",
            "expected_story_ids": ["story-1"],
            "planted_claims": [],
            "planted_claim_class": None,
        }
    ]
    payload = {
        "records": [
            {
                "case_id": "case-1",
                "intent": "authority",
                "draft": "Draft",
                "stories": [{"id": "story-1"}],
                "claims_report": {"unresolved": []},
                "voice_report": {
                    "features": {"first_person_rate": 0.1},
                    "scored_features": ["first_person_rate"],
                    "baseline_features": {"first_person_rate": {"mean": 0.1, "stdev": 0.1}},
                },
                "node_path": [
                    "profile_memory", "intake_router", "ground", "write", "gate", "critique", "hitl"
                ],
                "cost_usd": 0.01,
                "latency_seconds": 12.0,
                "trace_metadata": {"error_classes": []},
            }
        ]
    }
    rows = case_rows(payload, cases)
    summary = aggregate(rows)
    assert rows[0]["story_top1"] == 1.0
    assert rows[0]["delivered"] is True
    assert summary["story_top1"] == 1.0
    assert summary["cost_mean_usd"] == 0.01


def test_wilson_interval_requires_a_denominator() -> None:
    assert wilson_interval(0, 0) == (None, None)
    low, high = wilson_interval(21, 21)
    assert low is not None and high == 1.0
