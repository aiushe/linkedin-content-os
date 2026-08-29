"""The authored skills layer must be loaded by the graph, not re-implemented inside it."""

from __future__ import annotations

from agent import skills

ALL_ELEVEN = {
    "authority-post", "comment-drafter", "hook-lab", "image-brief", "jd-keyword-miner",
    "post-templatizer", "profile-rewriter", "reach-post", "story-bank-curator",
    "target-mapper", "voice-check",
}


def test_every_authored_skill_is_discovered() -> None:
    assert set(skills.available()) == ALL_ELEVEN


def test_every_skill_is_reachable_from_some_role() -> None:
    """No authored skill may be orphaned — that is how the layer got dropped before."""
    mapped = {name for names in skills.ROLE_SKILLS.values() for name in names}
    assert ALL_ELEVEN - mapped == set(), f"orphaned skills: {ALL_ELEVEN - mapped}"


def test_profile_rewriter_reference_files_load() -> None:
    skill = skills.load("profile-rewriter")
    assert skill is not None
    assert len(skill.references) == 6
    assert "recruiter-lens" in skill.references


def test_role_block_carries_the_evidence_boundary() -> None:
    block = skills.role_block("authority")
    assert "authority-post" in block and "hook-lab" in block
    assert "never justify a factual claim" in block


def test_manifest_is_frontmatter_only() -> None:
    """Progressive disclosure: the catalogue must not drag in full skill bodies."""
    manifest = skills.manifest_block()
    assert "jd-keyword-miner" in manifest
    assert "Hard focus gate" not in manifest


def test_missing_skill_degrades() -> None:
    assert skills.load("does-not-exist") is None
    assert skills.for_role("nonsense-role") == []
