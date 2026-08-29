"""Embedding provider selection: OpenAI by default, Voyage still reachable."""

from __future__ import annotations

from pipeline import embed


def test_defaults_are_current_not_deprecated_models() -> None:
    """voyage-3 / voyage-multimodal-3 are deprecated and outside Voyage's free tier."""
    assert embed.DEFAULT_TEXT_MODEL["openai"] == "text-embedding-3-small"
    assert embed.DEFAULT_TEXT_MODEL["voyage"] != "voyage-3"
    assert embed.DEFAULT_MULTIMODAL_MODEL != "voyage-multimodal-3"


def test_text_model_override_beats_provider_default(monkeypatch) -> None:
    monkeypatch.setenv("EMBED_MODEL_OVERRIDE", "Qwen/Qwen3-Embedding-8B")
    assert embed.resolve_text_model("openai") == "Qwen/Qwen3-Embedding-8B"
    assert embed.resolve_text_model("openai", "explicit-model") == "explicit-model"


def test_openai_payload_omits_voyage_only_field(monkeypatch) -> None:
    seen = {}

    class Resp:
        def raise_for_status(self): ...
        def json(self):
            return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, payload=json)
        return Resp()

    monkeypatch.setattr(embed.requests, "post", fake_post)
    out = embed.embed_text_batch(["hello"], "sk-test", "text-embedding-3-small", "openai")
    assert seen["url"] == embed.OPENAI_TEXT_ENDPOINT
    assert "input_type" not in seen["payload"], "input_type is Voyage-only"
    assert out == [[0.1, 0.2]]


def test_voyage_payload_keeps_input_type(monkeypatch) -> None:
    seen = {}

    class Resp:
        def raise_for_status(self): ...
        def json(self):
            return {"data": [{"index": 0, "embedding": [0.3]}]}

    monkeypatch.setattr(
        embed.requests, "post",
        lambda url, headers=None, json=None, timeout=None: (
            seen.update(url=url, payload=json),
            Resp(),
        )[1],
    )
    embed.embed_text_batch(["hi"], "pa-test", "voyage-3.5", "voyage")
    assert seen["url"] == embed.VOYAGE_TEXT_ENDPOINT
    assert seen["payload"]["input_type"] == "document"


def test_images_remain_voyage_only() -> None:
    """OpenAI publishes no multimodal embedding endpoint; the path is kept, not deleted."""
    assert embed.KEY_ENV["voyage"] == "VOYAGE_API_KEY"
    assert "multimodalembeddings" in embed.VOYAGE_MULTIMODAL_ENDPOINT


def test_batch_order_is_preserved(monkeypatch) -> None:
    class Resp:
        def raise_for_status(self): ...
        def json(self):
            return {"data": [
                {"index": 1, "embedding": [2.0]},
                {"index": 0, "embedding": [1.0]},
            ]}

    monkeypatch.setattr(
        embed.requests, "post", lambda *a, **k: Resp()
    )
    assert embed.embed_text_batch(["a", "b"], "k", "m", "openai") == [[1.0], [2.0]]
