"""Grounding must not spend on an observational ReAct trace by default."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.nodes import ground
from pipeline import common


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


def test_keyword_brief_parsing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The keyword brief loader parses role, concepts, keywords, and gaps."""
    monkeypatch.setattr(common, "PRIVATE", tmp_path / "private")
    monkeypatch.setattr(common, "ROOT", tmp_path)
    briefs_dir = tmp_path / "private" / "targets" / "briefs"
    briefs_dir.mkdir(parents=True)
    (briefs_dir / "2026-08-28-role-keywords.md").write_text(
        "# Role keyword brief\n\n"
        "- Role family: AI Product Manager\n\n"
        "## Concept coverage\n\n"
        "| Concept | JDs | Present in |\n"
        "| --- | --- | --- |\n"
        "| Agentic AI | 5/5 | all |\n"
        "| Evals | 4/5 | most |\n\n"
        "## Keywords by category\n\n"
        '**Role / domain** \u2014 agentic AI, LLM products, detection systems.\n\n'
        "## Positioning recommendation\n\n"
        "Lead with evals and measurement.\n\n"
        "## Honest gaps\n\n"
        "- **Revenue ownership.** No revenue claims in corpus.\n",
        encoding="utf-8",
    )
    brief = common.load_keyword_brief()
    assert brief is not None
    assert brief["role_family"] == "AI Product Manager"
    assert "Agentic AI" in brief["concepts"]
    assert "Evals" in brief["concepts"]
    assert "Role / domain" in brief["keywords_by_category"]
    assert "agentic AI" in brief["keywords_by_category"]["Role / domain"]
    assert brief["positioning"].startswith("Lead with evals")
    assert any("Revenue" in g for g in brief["honest_gaps"])


def test_keyword_brief_flows_into_grounding(
    synthetic_corpus, monkeypatch
) -> None:
    """When a keyword brief exists, it appears in grounding output."""
    fake_brief = {
        "role_family": "AI PM",
        "concepts": ["Agentic AI", "Evals"],
        "keywords_by_category": {"Role": ["agentic AI"]},
        "positioning": "Lead with evals.",
        "honest_gaps": ["Revenue ownership."],
        "path": "private/targets/briefs/test.md",
    }
    monkeypatch.setattr(ground, "load_keyword_brief", lambda: fake_brief)
    monkeypatch.setattr(ground, "should_fetch", lambda _: False)

    result = ground.ground({"idea": "A grounded product lesson.", "intent": "authority"})

    assert result["keyword_brief"] == fake_brief


def test_keyword_brief_absent_when_no_file(synthetic_corpus, monkeypatch) -> None:
    """When no keyword brief exists, the field is absent from output."""
    monkeypatch.setattr(ground, "load_keyword_brief", lambda: None)
    monkeypatch.setattr(ground, "should_fetch", lambda _: False)

    result = ground.ground({"idea": "A grounded product lesson.", "intent": "authority"})

    assert result.get("keyword_brief") is None
