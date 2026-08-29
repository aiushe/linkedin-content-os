"""Model-client safety defaults."""

from __future__ import annotations

import sys
import time
from types import SimpleNamespace

import pytest

from agent import config, models


def test_model_factory_bounds_each_provider_request(monkeypatch) -> None:
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "langchain_openai", SimpleNamespace(ChatOpenAI=FakeChatOpenAI))

    models.get_model("writer")

    assert captured["timeout"] == config.LLM_TIMEOUT_SECONDS
    assert captured["max_retries"] == 0
    assert captured["temperature"] == config.WRITER_TEMPERATURE


def test_model_factory_forwards_an_explicit_seed(monkeypatch) -> None:
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "langchain_openai", SimpleNamespace(ChatOpenAI=FakeChatOpenAI))
    monkeypatch.setattr(config, "LLM_SEED", 17)

    models.get_model("writer")

    assert captured["seed"] == 17


def test_hard_deadline_interrupts_a_blocking_main_thread_call(monkeypatch) -> None:
    monkeypatch.setattr(config, "LLM_HARD_TIMEOUT_SECONDS", 0.01)

    with pytest.raises(models.ModelDeadlineExceeded):
        models.invoke_with_deadline(lambda: time.sleep(1))
