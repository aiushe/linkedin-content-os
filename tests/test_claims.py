from agent import config
from pipeline import claims


def test_parser_only_allows_verified_five_column_rows():
    allowed, narrative = claims.parse_truth_table(
        """| Claim | Proof/source | Date | Verified | Notes |
| --- | --- | --- | --- | --- |
| Reduced time by 40% | dashboard | 2026 | yes | safe |
| [placeholder] | source | 2026 | yes | no |

## Narrative-only facts
| Fact | Why not verified | Follow-up |
| --- | --- | --- |
| Built the first prototype | no proof | find record |
"""
    )
    assert [fact.claim for fact in allowed] == ["Reduced time by 40%"]
    assert narrative == {"Built the first prototype"}


def test_load_allowlist_ignores_unverified_story_metrics(synthetic_corpus):
    facts = claims.load_allowlist()
    assert any(fact.claim == "Reduced routing time by 30%" for fact in facts)
    assert not any("90%" in fact.claim for fact in facts)


def test_exact_numeric_matching_blocks_near_miss(synthetic_corpus):
    allowed = claims.load_allowlist()
    assert claims.check("I reduced routing time by 30%.", allowed).verdict == "pass"
    report = claims.check("I reduced routing time by 31%.", allowed)
    assert report.verdict == "block"
    assert [claim.span for claim in report.unmatched] == ["31%"]


def test_claim_matching_mode_is_read_and_never_accepts_a_near_miss(synthetic_corpus, monkeypatch):
    monkeypatch.setattr(config, "CLAIM_REQUIRE_EXACT", False)

    report = claims.check("I reduced routing time by 31%.", claims.load_allowlist())

    assert report.verdict == "block"


def test_empty_allowlist_is_indeterminate(synthetic_corpus):
    assert claims.check("A plain draft.", []).verdict == "indeterminate"


def test_frontmatter_review_notes_and_years_are_not_claims(synthetic_corpus):
    report = claims.check(
        """---
created_at: 2026
metric: 99%
---
I learned this in 2026.

## Review notes
- Claims checked: 99%
""",
        claims.load_allowlist(),
    )
    assert report.claims == []


def test_list_marker_does_not_become_a_claim(synthetic_corpus):
    report = claims.check("1. Start with the decision.", claims.load_allowlist())
    assert report.claims == []


def test_superlative_is_blocked_without_exact_allowlist_match(synthetic_corpus):
    report = claims.check("I built the first workflow.", claims.load_allowlist())
    assert report.verdict == "block"
    assert report.unmatched[0].span.lower() == "first"


def test_enumerative_first_is_not_a_superlative_claim(synthetic_corpus):
    report = claims.check("First, make the decision rules visible.", claims.load_allowlist())
    assert report.verdict == "pass"
    assert report.unmatched == []


def test_temporal_at_first_is_not_a_superlative_claim(synthetic_corpus):
    report = claims.check(
        "What friction did not seem urgent at first?", claims.load_allowlist()
    )
    assert report.verdict == "pass"
    assert report.unmatched == []


def test_attribution_is_reported_but_not_made_up_as_a_numeric_block(synthetic_corpus):
    report = claims.check("Our data shows the workflow changed.", claims.load_allowlist())
    assert report.verdict == "pass"
    assert report.claims[0].kind == "attribution"


def test_narrative_only_context_blocks_quantification(synthetic_corpus):
    report = claims.check(
        "I volunteered to build product demos 2x faster while in support.", claims.load_allowlist()
    )
    assert report.verdict == "block"
    assert report.narrative_only_hits
