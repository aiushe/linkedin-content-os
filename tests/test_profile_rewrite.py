"""The profile-rewrite role family must pass a deterministic JD-focus gate."""

from __future__ import annotations

from agent.nodes import profile_rewrite


def _write_jds(directory, documents: list[str]) -> None:
    directory.mkdir(parents=True)
    for index, document in enumerate(documents, start=1):
        (directory / f"jd-{index}.md").write_text(document, encoding="utf-8")


def test_scattered_jds_halt_before_profile_copy(monkeypatch, tmp_path) -> None:
    jd_dir = tmp_path / "private" / "targets" / "jds"
    _write_jds(
        jd_dir,
        [
            "Product Manager agentic evaluations reliable systems",
            "Product Operations revenue planning sales enablement",
            "Technical Program Manager infrastructure reliability delivery",
            "Product Manager privacy classification detection systems",
            "Product Manager procurement workflow marketplace partnerships",
        ],
    )
    monkeypatch.setattr(profile_rewrite.common, "PRIVATE", tmp_path / "private")

    result = profile_rewrite.profile_rewrite({"intent": "profile_rewrite"})

    assert result["profile_analysis"]["coverage"] < 0.75
    assert result["errors"][0]["class"] == "focus"
    assert result["terminal_reason"].startswith("Profile rewrite stopped")
    assert "product operations" in result["terminal_reason"]
    assert "draft" not in result


def test_converged_jds_pass_the_focus_gate(tmp_path) -> None:
    jd_dir = tmp_path / "jds"
    _write_jds(jd_dir, ["Agentic evaluation platform reliability ownership"] * 5)

    analysis = profile_rewrite.analyze_jds(jd_dir)

    assert analysis["coverage"] == 1.0
    assert analysis["focused"]
