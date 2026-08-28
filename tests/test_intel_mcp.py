"""Live intel must degrade, never claim to be scored, and never overspend."""

from __future__ import annotations

import json

from agent import config, intel_mcp

RAW = [
    {"content": ("word " * 300).strip(), "likes": 10, "comments": 1, "authorName": "A"},
    {"content": ("word " * 300).strip(), "likes": 900, "comments": 50, "authorName": "B"},
    {"content": ("word " * 300).strip(), "likes": 400, "comments": 5, "authorName": "C"},
    {"content": ("word " * 300).strip(), "likes": 50, "comments": 2, "authorName": "D"},
    {"content": ("word " * 300).strip(), "likes": 20, "comments": 0, "authorName": "E"},
    {"content": ("word " * 300).strip(), "likes": 5, "comments": 0, "authorName": "F"},
]


def _stub(payload):
    """Replace asyncio.run, closing the coroutine so pytest reports no warning."""

    def runner(coro, *_a, **_k):
        coro.close()
        return payload

    return runner


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(intel_mcp, "INTEL", tmp_path)
    monkeypatch.setenv("APIFY_API_TOKEN", "apify_api_fake")
    monkeypatch.delenv("AGENT_OFFLINE", raising=False)


def test_unavailable_without_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(intel_mcp, "INTEL", tmp_path)
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    result = intel_mcp.search_trending_posts("agentic product management")
    assert result["available"] is False and result["posts"] == []
    assert result["estimated_usd"] == 0.0


def test_intent_gate_allows_authority_but_blocks_comments() -> None:
    """Authority and reach get market shape; comments remain anchored to one post."""
    assert intel_mcp.should_fetch("reach") is True
    assert intel_mcp.should_fetch("authority") is True
    assert intel_mcp.should_fetch("comment") is False


def test_network_failure_degrades_not_raises(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)

    def boom(*_a, **_k):
        raise ConnectionError("dns failure")

    monkeypatch.setattr(intel_mcp.asyncio, "run", boom)
    result = intel_mcp.search_trending_posts("x")
    assert result["available"] is False and "ConnectionError" in result["reason"]


def test_compression_caps_context_and_never_scores(monkeypatch, tmp_path) -> None:
    """Control 4: only top-K truncated hooks reach a model, never full bodies."""
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(intel_mcp.asyncio, "run", _stub(RAW))
    result = intel_mcp.search_trending_posts("x")
    assert len(result["posts"]) == config.INTEL_TOP_K < len(RAW)
    assert result["posts"][0]["likes"] == 900, "must rank by engagement"
    assert len(result["structural_posts"]) == len(RAW)
    for post in result["posts"]:
        assert "text" not in post, "full post body must never reach an LLM context"
        assert len(post["hook"]) <= config.INTEL_HOOK_CHARS
        assert post["x_factor"] is None and post["scored"] is False
    for summary in result["structural_posts"]:
        assert set(summary) == {"word_count", "paragraphs", "opening_move"}


def test_cache_hit_is_free(monkeypatch, tmp_path) -> None:
    """Control 3: a repeat query inside the TTL costs nothing and makes no call."""
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(intel_mcp.asyncio, "run", _stub(RAW))
    first = intel_mcp.search_trending_posts("same topic")
    assert first["cached"] is False and first["estimated_usd"] > 0

    def must_not_call(*_a, **_k):
        raise AssertionError("cache hit must not reach the network")

    monkeypatch.setattr(intel_mcp.asyncio, "run", must_not_call)
    second = intel_mcp.search_trending_posts("same topic")
    assert second["cached"] is True and second["estimated_usd"] == 0.0
    assert second["posts"] == first["posts"]


def test_max_posts_is_capped(monkeypatch, tmp_path) -> None:
    """Control 6: a caller cannot exceed the configured actor spend cap."""
    _isolate(monkeypatch, tmp_path)
    seen = {}

    def capture(coro, *_a, **_k):
        coro.close()
        seen["called"] = True
        return RAW

    monkeypatch.setattr(intel_mcp.asyncio, "run", capture)
    intel_mcp.search_trending_posts("y", max_posts=10_000)
    assert seen["called"]
    cached = json.loads(next(tmp_path.glob("cache/*.json")).read_text())
    assert cached["estimated_usd"] == round(len(RAW) * config.INTEL_USD_PER_POST, 5)
