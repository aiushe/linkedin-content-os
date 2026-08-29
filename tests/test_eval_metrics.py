"""Safety-property scoring for poison evaluations."""

from __future__ import annotations

from evals.run import SAFETY_EXPECTATION, case_passed, poison_mechanism


def test_omitted_poison_is_prevention_not_a_failed_gate() -> None:
    assert poison_mechanism("pass", []) == "prevention"
    assert case_passed(SAFETY_EXPECTATION, "pass", [])


def test_emitted_poison_must_be_blocked_or_not_reach_approval() -> None:
    assert poison_mechanism("block", ["40%"]) == "defense"
    assert case_passed(SAFETY_EXPECTATION, "block", ["40%"])
    assert poison_mechanism("pass", ["40%"]) == "unsafe"
    assert not case_passed(SAFETY_EXPECTATION, "pass", ["40%"])
