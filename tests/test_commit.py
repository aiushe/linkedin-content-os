from agent.nodes.commit import commit
from pipeline import common


def test_commit_writes_only_after_approval_and_updates_private_story(tmp_path, monkeypatch):
    private_story = tmp_path / "private" / "stories" / "synthetic.md"
    private_story.parent.mkdir(parents=True)
    private_story.write_text(
        "---\nid: synthetic\nused_in: []\n---\nSynthetic story.", encoding="utf-8"
    )
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "PRIVATE", tmp_path / "private")
    result = commit(
        {
            "decision": "approve",
            "gate_verdict": "pass",
            "intent": "authority",
            "draft": "A grounded draft.",
            "hooks": ["One", "Two", "Three", "Four", "Five"],
            "stories": [
                {"id": "synthetic", "pillars": ["test"], "path": "private/stories/synthetic.md"}
            ],
            "template": None,
            "degradation_reasons": [],
            "critique": {},
        }
    )
    queued = tmp_path / result["queue_path"]
    assert queued.exists()
    assert "claims_checked: true" in queued.read_text(encoding="utf-8")
    assert queued.stem in private_story.read_text(encoding="utf-8")


def test_commit_refuses_without_explicit_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    result = commit({"decision": "retry", "gate_verdict": "pass"})
    assert result["terminal_reason"] == "Commit blocked: approval was not received."
    assert not (tmp_path / "drafts").exists()
