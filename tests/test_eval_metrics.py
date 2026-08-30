"""Detection-quality scoring for advisory claim evaluations."""

from __future__ import annotations

from evals.run import case_passed


def test_detected_poison_is_scored_by_claim_recall_and_delivery() -> None:
    assert case_passed(
        {
            "kind": "poison",
            "planted_claims": ["40%"],
            "planted_detected": ["40%"],
            "draft_produced": True,
            "reached_user": True,
        }
    )


def test_clean_flag_or_missing_delivery_is_not_a_pass() -> None:
    assert not case_passed(
        {
            "kind": "clean",
            "clean_unflagged": False,
            "draft_produced": True,
            "reached_user": True,
        }
    )
    assert not case_passed(
        {
            "kind": "poison",
            "planted_claims": ["40%"],
            "planted_detected": ["40%"],
            "draft_produced": True,
            "reached_user": False,
        }
    )
