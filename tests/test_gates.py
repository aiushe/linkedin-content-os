from agent import gates
from pipeline.claims import AllowedFact


def test_safe_voice_score_fails_closed_when_fingerprint_empty(monkeypatch):
    monkeypatch.setattr(gates.voice, "load_fingerprint", lambda: {})
    result = gates.safe_voice_score("A simple draft.")
    assert result["verdict"] == "indeterminate"


def test_safe_voice_score_deduplicates_tells(monkeypatch):
    profile = {
        "sample_count": 3,
        "word_count": 1500,
        "features": {"example": {"mean": 0, "stdev": 0}},
    }
    monkeypatch.setattr(gates.voice, "load_fingerprint", lambda: profile)
    monkeypatch.setattr(
        gates.voice,
        "score_text",
        lambda draft, profile: {
            "features": {},
            "flags": [],
            "banned_tells": [
                "Tell",
                "tell",
                "rhetorical-question openers",
                "rhetorical-question opener",
            ],
        },
    )
    result = gates.safe_voice_score("Draft")
    assert result["verdict"] == "revise"
    assert result["banned_tells"] == ["Tell", "rhetorical-question openers"]


def test_claim_block_dominates_voice_indeterminate(monkeypatch):
    monkeypatch.setattr(gates.voice, "load_fingerprint", lambda: {})
    report = gates.gate(
        "I improved routing by 99%.",
        [
            AllowedFact(
                claim="Reduced routing by 30%",
                proof="proof",
                period="2026",
                source="truth_table",
                source_ref="test",
            )
        ],
    )
    assert report.verdict == "block"


def test_reduce_verdicts_precedence():
    assert gates.reduce_verdicts({"verdict": "revise"}, {"verdict": "block"}) == "block"
    assert (
        gates.reduce_verdicts({"verdict": "indeterminate"}, {"verdict": "pass"}) == "indeterminate"
    )
    assert gates.reduce_verdicts({"verdict": "revise"}, {"verdict": "pass"}) == "revise"
