"""Grounding must not spend on an observational ReAct trace by default."""

from __future__ import annotations

from agent.nodes import ground


def test_live_grounding_skips_discarded_react_trace_by_default(
    synthetic_corpus, monkeypatch
) -> None:
    monkeypatch.setattr(ground.config, "live_models_enabled", lambda: True)
    monkeypatch.setattr(ground.config, "GROUND_REACT_TRACE_ENABLED", False)
    monkeypatch.setattr(ground, "should_fetch", lambda _: False)
    monkeypatch.setattr(
        ground,
        "_run_live_react",
        lambda *_: (_ for _ in ()).throw(AssertionError("trace should be disabled")),
    )

    result = ground.ground({"idea": "A grounded product lesson.", "intent": "authority"})

    assert result["stories"]
    assert result["cost_events"][0]["model"] == "trace_disabled"
