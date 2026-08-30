from __future__ import annotations

from agent.gates import gate, reduce_verdicts
from pipeline import claims, confidential


def test_absent_confidential_terms_are_clean_and_non_blocking(monkeypatch):
    monkeypatch.setattr(confidential, "load_terms", lambda: None)

    report = confidential.check("A grounded draft.")

    assert report.verdict == "pass"
    assert "not configured" in report.reason


def test_confidential_match_warns_and_reports_the_term_and_lines(monkeypatch):
    monkeypatch.setattr(confidential, "load_terms", lambda: {"Internal Codename"})

    report = confidential.check("A lesson from Internal Codename.\nInternal Codename was useful.")

    assert report.verdict == "warn"
    assert report.matched_terms == ["Internal Codename"]
    assert report.matched_lines == {"Internal Codename": [1, 2]}


def test_confidential_gate_cannot_block_an_otherwise_passing_draft(monkeypatch):
    monkeypatch.setattr(confidential, "load_terms", lambda: {"Internal Codename"})
    monkeypatch.setattr(
        "agent.gates.safe_voice_score",
        lambda _, **kwargs: {"verdict": "pass", "flags": [], "banned_tells": []},
    )

    report = gate(
        "Internal Codename taught me a useful lesson.",
        [
            claims.AllowedFact(
                claim="A grounded fact",
                proof="test proof",
                period="2026",
                source="truth_table",
                source_ref="test",
            )
        ],
    )

    assert report.verdict == "pass"
    assert report.confidential.verdict == "warn"


def test_confidential_verdict_is_ignored_even_if_it_is_misreported_as_block():
    assert reduce_verdicts(
        {"verdict": "pass"}, {"verdict": "pass"}, {"verdict": "block"}
    ) == "pass"


def test_claims_gate_still_can_block():
    assert reduce_verdicts(
        {"verdict": "pass"}, {"verdict": "block"}, {"verdict": "warn"}
    ) == "block"
