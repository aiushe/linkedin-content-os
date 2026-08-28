"""Live model smoke test.

Skipped without network or a key, but it is NOT forced offline. Its purpose is to
make "the model path actually works" something the suite asserts instead of assumes.
"""

from __future__ import annotations

import os
import socket

import pytest

from agent import config


def _openai_reachable() -> bool:
    try:
        socket.create_connection(("api.openai.com", 443), timeout=5).close()
        return True
    except OSError:
        return False


live = pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") and _openai_reachable()),
    reason="needs OPENAI_API_KEY and network access to api.openai.com",
)


@live
def test_env_key_is_loaded_without_quotes() -> None:
    key = os.environ["OPENAI_API_KEY"]
    assert not key.startswith('"'), ".env value is quoted; dotenv should have stripped it"
    assert key.startswith("sk-")


@live
def test_router_makes_a_real_call(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_OFFLINE", raising=False)
    assert config.live_models_enabled()
    from agent.nodes.router import intake_router

    result = intake_router(
        {
            "idea": "a post about moving from support into product",
            "thread_id": "smoke",
            "revision": 0,
        }
    )
    assert not result["errors"], f"router failed live: {result['errors']}"
    assert result["intent_confidence"] > 0.0, "confidence 0.0 means the model call failed"
    event = result["cost_events"][0]
    assert event["prompt_tokens"] > 0, "zero tokens means no model was actually invoked"
