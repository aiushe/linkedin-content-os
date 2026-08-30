from agent.nodes.commit import commit
from pipeline import common


def test_commit_writes_only_queue_artifact_after_approval(tmp_path, monkeypatch):
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
            "claims_report": {
                "verdict": "pass",
                "unresolved": [],
                "matched": [
                    [
                        {
                            "span": "30%",
                            "kind": "numeric",
                            "sentence": "I reduced routing time by 30%.",
                            "line_no": 1,
                        },
                        {
                            "claim": "Reduced routing time by 30%",
                            "source": "truth_table",
                            "source_ref": "private/identity/truth-table.md",
                        },
                    ]
                ],
            },
            "voice_report": {"verdict": "pass"},
            "confidential_report": {"verdict": "pass"},
            "market_brief": {"available": False, "reason": "No market records."},
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
    assert "confidential_terms_check: pass" in queued.read_text(encoding="utf-8")
    assert "observations_claims_grounded:" in queued.read_text(encoding="utf-8")
    assert "observations_voice:" in queued.read_text(encoding="utf-8")
    assert "observations_market:" in queued.read_text(encoding="utf-8")
    assert private_story.read_text(encoding="utf-8").endswith("Synthetic story.")


def test_commit_does_not_save_without_explicit_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    result = commit({"decision": "retry", "gate_verdict": "pass"})
    assert result["terminal_reason"] == "Draft was not saved because approval was not received."
    assert not (tmp_path / "drafts").exists()


def test_commit_saves_unresolved_claim_observations_without_a_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "ROOT", tmp_path)

    result = commit(
        {
            "decision": "approve",
            "claims_report": {"unresolved": [{"span": "40%"}]},
            "draft": "A draft with a 40% claim.",
            "hooks": [],
            "degradation_reasons": [],
            "critique": {},
        }
    )

    saved = (tmp_path / result["queue_path"]).read_text(encoding="utf-8")
    assert 'unresolved_claim_spans: ["40%"]' in saved
    assert "observations_claims_not_grounded:" in saved
