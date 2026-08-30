from agent import gates
from pipeline.claims import AllowedFact


def test_safe_voice_score_reports_when_fingerprint_empty(monkeypatch):
    monkeypatch.setattr(gates.voice, "load_fingerprint", lambda: {})
    result = gates.safe_voice_score("A simple draft.")
    assert result["verdict"] == "warn"


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


def test_short_post_excludes_paragraph_shape_from_voice_scoring(monkeypatch):
    profile = {
        "sample_count": 3,
        "word_count": 1500,
        "features": {
            "paragraph_length_mean": {"mean": 379.7, "stdev": 129.4},
            "paragraph_length_stdev": {"mean": 0.0, "stdev": 1.0},
            "first_person_rate": {"mean": 0.039, "stdev": 0.1},
        },
    }
    monkeypatch.setattr(gates.voice, "load_fingerprint", lambda: profile)
    monkeypatch.setattr(
        gates.voice,
        "score_text",
        lambda draft, profile: {
            "features": {
                "paragraph_length_mean": 28.1,
                "paragraph_length_stdev": 8.0,
                "first_person_rate": 0.039,
            },
            "flags": [],
            "banned_tells": [],
        },
    )

    result = gates.safe_voice_score("A short LinkedIn post.", target_format="short_post")

    assert result["verdict"] == "pass"
    assert result["flags"] == []
    assert result["excluded_features"] == [
        "paragraph_length_mean",
        "paragraph_length_stdev",
    ]
    assert result["scored_features"] == ["first_person_rate"]


def test_short_post_keeps_first_person_rate_in_voice_scoring(monkeypatch):
    profile = {
        "sample_count": 3,
        "word_count": 1500,
        "features": {
            "paragraph_length_mean": {"mean": 379.7, "stdev": 129.4},
            "paragraph_length_stdev": {"mean": 0.0, "stdev": 1.0},
            "first_person_rate": {"mean": 0.039, "stdev": 0.01},
        },
    }
    monkeypatch.setattr(gates.voice, "load_fingerprint", lambda: profile)
    monkeypatch.setattr(
        gates.voice,
        "score_text",
        lambda draft, profile: {
            "features": {
                "paragraph_length_mean": 28.1,
                "paragraph_length_stdev": 8.0,
                "first_person_rate": 0.005,
            },
            "flags": [],
            "banned_tells": [],
        },
    )

    result = gates.safe_voice_score("A short LinkedIn post.", target_format="short_post")

    assert result["verdict"] == "revise"
    assert [flag["feature"] for flag in result["flags"]] == ["first_person_rate"]


def test_claim_warning_and_missing_voice_profile_stay_advisory(monkeypatch):
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
    assert report.verdict == "warn"


def test_reduce_verdicts_precedence():
    assert gates.reduce_verdicts({"verdict": "revise"}, {"verdict": "warn"}) == "warn"
    assert gates.reduce_verdicts({"verdict": "warn"}, {"verdict": "pass"}) == "warn"
    assert gates.reduce_verdicts({"verdict": "revise"}, {"verdict": "pass"}) == "revise"
