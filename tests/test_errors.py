import pytest

from agent.errors import AgentFailure, FailureClass, retry_delay, should_retry, with_retry


def test_only_transient_failures_retry():
    transient = AgentFailure(FailureClass.TRANSIENT, "timeout")
    integrity = AgentFailure(FailureClass.INTEGRITY, "ungrounded")
    assert should_retry(transient, 0)
    assert should_retry(transient, 1)
    assert not should_retry(transient, 2)
    assert not should_retry(integrity, 0)
    assert retry_delay(1) > retry_delay(0)


def test_with_retry_retries_then_returns():
    attempts = []

    def operation():
        attempts.append(1)
        if len(attempts) < 3:
            raise AgentFailure(FailureClass.TRANSIENT, "temporary")
        return "ok"

    assert with_retry(operation, sleep=lambda _: None) == "ok"
    assert len(attempts) == 3


def test_with_retry_never_retries_integrity():
    with pytest.raises(AgentFailure):
        with_retry(
            lambda: (_ for _ in ()).throw(AgentFailure(FailureClass.INTEGRITY, "unsafe")),
            sleep=lambda _: None,
        )
