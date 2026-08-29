"""Ops workflow stays manual and cannot write outreach activity."""

from __future__ import annotations

from agent.nodes import outreach


def test_outreach_requires_an_application_first(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(outreach.common, "ROOT", tmp_path)

    result = outreach.outreach({"idea": "Map outreach contacts for this role."})

    assert result["errors"][0]["class"] == "sequence"
    assert result["ops_guidance"]["manual_only"]
    assert "queue_path" not in result


def test_outreach_exposes_only_existing_manual_surfaces(monkeypatch, tmp_path) -> None:
    (tmp_path / "ops").mkdir()
    (tmp_path / outreach.OUTREACH_LOG).write_text("# Outreach log\n", encoding="utf-8")
    (tmp_path / outreach.ENGAGEMENT_QUEUE).write_text("# Engagement queue\n", encoding="utf-8")
    monkeypatch.setattr(outreach.common, "ROOT", tmp_path)

    result = outreach.outreach({"idea": "I applied and need a target map."})

    assert result["ops_guidance"]["surfaces"] == {
        "outreach_log": outreach.OUTREACH_LOG,
        "engagement_queue": outreach.ENGAGEMENT_QUEUE,
    }
    assert result["ops_guidance"]["manual_only"]
