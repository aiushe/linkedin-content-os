from __future__ import annotations

from pathlib import Path

from scripts import audit


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_audit_detects_static_wiring_gaps(tmp_path: Path) -> None:
    _write(tmp_path / "agent" / "config.py", "LIVE = 1\nDEAD = 2\n")
    _write(
        tmp_path / "agent" / "state.py",
        "from typing import TypedDict\nclass DraftState(TypedDict):\n    unused: str\n",
    )
    _write(tmp_path / "agent" / "used.py", "from agent import config\nvalue = config.LIVE\n")
    _write(tmp_path / "agent" / "orphan.py", "value = 1\n")
    _write(tmp_path / "agent" / "skills.py", "ROLE_SKILLS = {'role': ('wired',)}\n")
    _write(tmp_path / "pipeline" / "tested.py", "value = 1\n")
    _write(tmp_path / "pipeline" / "untested.py", "value = 1\n")
    _write(
        tmp_path / "mcp" / "server.py",
        "class M: \n    def tool(self): return lambda f: f\nmcp = M()\n"
        "@mcp.tool()\ndef unwired(): pass\n",
    )
    _write(tmp_path / ".claude" / "skills" / "wired" / "SKILL.md")
    _write(tmp_path / ".claude" / "skills" / "orphan" / "SKILL.md")
    _write(tmp_path / "tests" / "test_used.py", "from pipeline import tested\n")

    findings = audit.orphan_modules(tmp_path)
    categories = {(finding.category, finding.detail) for finding in findings}
    assert ("orphan modules", "agent/orphan.py") in categories
    assert audit.dead_config(tmp_path) == [audit.Finding("dead config", "DEAD")]
    assert audit.orphan_skills(tmp_path) == [audit.Finding("orphan skills", "orphan")]
    assert audit.unwired_mcp_tools(tmp_path) == [audit.Finding("unwired MCP tools", "unwired")]
    assert set(audit.untested_modules(tmp_path)) == {
        audit.Finding("untested modules", "agent/config.py"),
        audit.Finding("untested modules", "agent/orphan.py"),
        audit.Finding("untested modules", "agent/skills.py"),
        audit.Finding("untested modules", "agent/state.py"),
        audit.Finding("untested modules", "agent/used.py"),
        audit.Finding("untested modules", "pipeline/untested.py"),
        audit.Finding("untested modules", "mcp/server.py"),
    }
    assert audit.unread_state_fields(tmp_path) == [audit.Finding("unread state fields", "unused")]


def test_audit_reports_broken_docs_markers_and_ungated_queue(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "See `docs/missing.md`.\n")
    _write(tmp_path / "PLAN.md", "Build `intel/reports/top-posts.md`.\n")
    _write(tmp_path / "agent" / "config.py")
    _write(
        tmp_path / "agent" / "state.py",
        "from typing import TypedDict\nclass DraftState(TypedDict):\n    pass\n",
    )
    _write(tmp_path / "mcp" / "server.py")
    _write(tmp_path / "pipeline" / "marker.py", "# TODO: test\n")
    _write(tmp_path / "drafts" / "queue" / "manual.md", "# manual\n")

    assert audit.broken_doc_references(tmp_path) == [
        audit.Finding("broken doc references", "README.md → docs/missing.md"),
    ]
    assert audit.missing_plan_outputs(tmp_path) == [
        audit.Finding("missing PLAN outputs", "intel/reports/top-posts.md")
    ]
    assert audit.markers(tmp_path) == [audit.Finding("debt markers", "pipeline/marker.py:1")]
    assert audit.ungated_artifacts(tmp_path) == [
        audit.Finding("ungated queue artifacts", "drafts/queue/manual.md")
    ]


def test_private_path_with_a_tracked_template_is_a_required_configuration(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "Configure `private/confidential-terms.md`.\n")
    _write(tmp_path / "corpus" / "identity" / "confidential-terms.md", "# Template\n")

    assert audit.broken_doc_references(tmp_path) == []
