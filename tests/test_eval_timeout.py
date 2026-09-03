"""Live-eval process deadline result semantics."""

from __future__ import annotations

from types import SimpleNamespace

from evals import run as run_module
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


def test_timeout_interrupts_before_forced_termination(monkeypatch) -> None:
    calls: list[object] = []

    class FakeQueue:
        def close(self) -> None:
            calls.append("queue.close")

    class FakeProcess:
        pid = 4321

        def start(self) -> None:
            calls.append("start")

        def join(self, timeout: float | None = None) -> None:
            calls.append(("join", timeout))

        def is_alive(self) -> bool:
            return "terminate" not in calls

        def terminate(self) -> None:
            calls.append("terminate")

    fake_context = SimpleNamespace(
        Queue=FakeQueue,
        Process=lambda **_: FakeProcess(),
    )
    monkeypatch.setattr(run_module.multiprocessing, "get_context", lambda _: fake_context)
    monkeypatch.setattr(run_module.os, "kill", lambda pid, sig: calls.append(("signal", pid, sig)))

    result = run_module.run_live_case(
        {"id": "timed", "kind": "clean", "planted_claims": []}, timeout_seconds=0
    )

    assert not result["passed"]
    assert calls[:3] == ["start", ("join", 0), ("signal", 4321, run_module.signal.SIGINT)]
    assert ("join", 5) in calls
    assert calls.index("terminate") > calls.index(("join", 5))
