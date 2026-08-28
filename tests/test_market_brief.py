"""Market briefs are useful only when their boundary with factual grounding holds."""

from __future__ import annotations

from dataclasses import asdict

from agent import market_brief
from agent.nodes import ground
from pipeline.claims import AllowedFact, check


def _brief(**overrides):
    values = {
        "available": True,
        "reason": "",
        "topic": "agent product",
        "window": "week",
        "post_count": 5,
        "topic_alive": False,
        "median_word_count": 180,
        "median_paragraphs": 6,
        "hook_moves": {"scene_or_claim": 3, "question": 1, "number": 1},
        "fingerprint_hook_moves": {"scene_or_claim": 2, "question": 0, "number": 1},
        "hook_alignment": "consistent",
        "saturated_angles": ["MCP tutorial"],
        "open_angles": ["enforcement mechanics"],
        "current_vocabulary": ["context engineering"],
        "exemplars": [{"hook": "We cut resolution time by 40%", "post_url": "https://x"}],
    }
    values.update(overrides)
    return market_brief.MarketBrief(**values)


def test_market_context_cannot_widen_the_factual_allowlist() -> None:
    """The market's 40% is still blocked when it is absent from verified evidence."""

    brief = _brief()
    assert "40%" in brief.exemplars[0]["hook"]
    allowlist = [
        AllowedFact(
            claim="Reduced routing time by 30%",
            proof="dashboard",
            period="2026-Q1",
            source="truth_table",
            source_ref="truth-table.md",
        )
    ]
    assert check("We cut resolution time by 40%.", allowlist).verdict == "block"


def test_brief_is_never_scored_and_exemplars_never_include_post_bodies(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    monkeypatch.setattr(
        market_brief.intel_mcp,
        "search_trending_posts",
        lambda *_a, **_k: {
            "available": True,
            "posts": [
                {
                    "text": "must not survive",
                    "hook": "A safe compressed hook",
                    "word_count": 100,
                    "paragraphs": 4,
                    "post_url": "https://example.test/post",
                }
            ],
            "structural_posts": [
                {"word_count": 100, "paragraphs": 4, "opening_move": "scene_or_claim"}
                for _ in range(12)
            ],
            "fetched_count": 12,
            "estimated_usd": 0.0,
        },
    )
    brief = market_brief.build("A useful agent lesson", "authority")
    assert brief.scored is False
    assert brief.post_count == 12 and brief.topic_alive is True
    assert all("text" not in exemplar for exemplar in brief.exemplars)


def test_comment_intent_never_fetches(monkeypatch) -> None:
    monkeypatch.setattr(
        market_brief.intel_mcp,
        "search_trending_posts",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )
    assert market_brief.should_fetch("comment") is False
    assert market_brief.build("Reply to this post", "comment").available is False


def test_saturation_failure_returns_empty_angles(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENT_OFFLINE", raising=False)

    class BrokenModel:
        def __init__(self, **_kwargs):
            pass

        def with_structured_output(self, _schema):
            return self

        def invoke(self, _prompt):
            raise RuntimeError("model unavailable")

    import langchain_openai

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", BrokenModel)
    assert market_brief.saturation(["A hook that is safe to classify"]) == ([], [])


def test_unavailable_brief_renders_no_writer_context() -> None:
    assert market_brief.render_prompt_block(_brief(available=False, reason="no token")) == ""


def test_query_is_deterministic_and_within_actor_limits() -> None:
    idea = "How I used agentic workflows to make product decisions"
    first = market_brief.derive_query(idea, "AI product")
    assert first == market_brief.derive_query(idea, "AI product")
    assert len(first) <= 500
    assert len(market_brief.BOOLEAN_OPERATOR_RE.findall(first)) <= 5


def test_ground_does_not_refetch_market_brief_in_revision(monkeypatch, synthetic_corpus) -> None:
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    calls = 0

    def fake_build(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return _brief()

    monkeypatch.setattr(ground, "build_market_brief", fake_build)
    state = {
        "idea": "A grounded product lesson.",
        "intent": "authority",
        "revision": 0,
        "market_fetched": False,
    }
    first = ground.ground(state)
    state.update(first)
    state["revision"] = 1
    ground.ground(state)
    assert calls == 1
    assert state["market_fetched"] is True
    assert first["market_brief"] == asdict(_brief())
