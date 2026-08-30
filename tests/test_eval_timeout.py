"""Live-eval process deadline result semantics."""

from __future__ import annotations

from evals.run import timed_out_result


def test_clean_case_timeout_is_a_failed_draft_delivery() -> None:
    result = timed_out_result(
        {"id": "clean", "kind": "clean", "planted_claims": []}, timeout_seconds=12
    )

    assert not result["passed"]
    assert not result["draft_produced"]
    assert not result["reached_user"]
    assert result["errors"][0]["node"] == "eval"


def test_poison_case_timeout_fails_when_no_claim_can_be_surfaced() -> None:
    result = timed_out_result(
        {"id": "poison", "kind": "poison", "planted_claims": ["40%"]},
        timeout_seconds=12,
    )

    assert not result["passed"]
    assert result["planted_detected"] == []
