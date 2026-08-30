from __future__ import annotations

from agent.gates import gate
from pipeline import confidential


def test_absent_confidential_terms_are_indeterminate(monkeypatch):
    monkeypatch.setattr(confidential, "load_terms", lambda: None)

    report = confidential.check("A grounded draft.")

    assert report.verdict == "indeterminate"
    assert "not configured" in report.reason


def test_confidential_match_blocks_and_reports_the_term(monkeypatch):
    monkeypatch.setattr(confidential, "load_terms", lambda: {"Restricted Account"})

    report = confidential.check("A lesson from Restricted Account.")

    assert report.verdict == "block"
    assert report.matched_terms == ["Restricted Account"]


def test_confidential_gate_prevents_anotherwise_passing_draft(monkeypatch):
    monkeypatch.setattr(confidential, "load_terms", lambda: {"Restricted Account"})
    monkeypatch.setattr(
        "agent.gates.safe_voice_score",
        lambda _: {"verdict": "pass", "flags": [], "banned_tells": []},
    )

    report = gate("Restricted Account taught me a useful lesson.", [])

    assert report.verdict == "block"
    assert report.confidential.matched_terms == ["Restricted Account"]
