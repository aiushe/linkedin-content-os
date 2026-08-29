"""Live-eval process deadline result semantics."""

from __future__ import annotations

from evals.run import SAFETY_EXPECTATION, timed_out_result


def test_clean_case_timeout_is_a_failed_escalation() -> None:
    result = timed_out_result(
        {"id": "clean", "kind": "clean", "expected": "pass"}, timeout_seconds=12
    )

    assert result["actual"] == "escalate"
    assert not result["passed"]
    assert result["errors"][0]["node"] == "eval"


def test_poison_case_timeout_is_safe_containment() -> None:
    result = timed_out_result(
        {"id": "poison", "kind": "poison", "expected": SAFETY_EXPECTATION}, timeout_seconds=12
    )

    assert result["passed"]
    assert result["poison_mechanism"] == "containment"
