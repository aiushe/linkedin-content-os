from langgraph.types import Command

from agent import config
from agent import graph as graph_module
from agent.graph import build_graph
from agent.nodes.hitl import VALID_ACTIONS, _review_payload
from pipeline import common


def test_clean_draft_reaches_human_interrupt(synthetic_corpus, monkeypatch):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "clean"}}
    graph.invoke(
        {
            "idea": "I reduced routing time by 30% by treating labels as product decisions.",
            "thread_id": "clean",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )
    state = graph.get_state(run_config).values
    assert state["gate_verdict"] == "pass"
    assert state["draft"]
    assert not state.get("queue_path")


def test_high_revision_count_still_reaches_the_human_without_an_automatic_loop(
    synthetic_corpus, monkeypatch
):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "revision-four"}}

    graph.invoke(
        {
            "idea": "I reduced routing time by 30% by treating labels as product decisions.",
            "thread_id": "revision-four",
            "forced_intent": "authority",
            "revision": 4,
        },
        config=run_config,
    )

    snapshot = graph.get_state(run_config)
    assert snapshot.values["draft"]
    assert snapshot.values["revision"] == 4
    assert snapshot.next == ("hitl",)
    assert not snapshot.values.get("terminal_reason")


def test_human_approval_is_required_before_graph_commits(synthetic_corpus, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "approval"}}
    graph.invoke(
        {
            "idea": "I reduced routing time by 30% by treating labels as product decisions.",
            "thread_id": "approval",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )
    assert not graph.get_state(run_config).values.get("queue_path")
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "PRIVATE", tmp_path / "private")
    graph.invoke(Command(resume={"action": "approve"}), config=run_config)
    state = graph.get_state(run_config).values
    assert state["queue_path"].startswith("drafts/queue/")
    assert (tmp_path / state["queue_path"]).exists()


def test_review_payload_contains_the_complete_human_approval_context():
    payload = _review_payload(
        {
            "draft": "A grounded draft.",
            "voice_report": {"verdict": "pass"},
            "claims_report": {"verdict": "pass"},
            "stories": [{"id": "story", "title": "Story", "path": "private/stories/story.md"}],
            "revision": 2,
            "cost_events": [{"node": "write", "usd": 0.0125}],
        }
    )

    assert payload["draft"] == "A grounded draft."
    assert payload["voice_report"]["verdict"] == "pass"
    assert payload["claims_report"]["verdict"] == "pass"
    assert payload["evidence"] == [
        {"id": "story", "title": "Story", "path": "private/stories/story.md"}
    ]
    assert payload["revision"] == 2
    assert payload["running_cost_usd"] == 0.0125
    assert set(payload["actions"]) == VALID_ACTIONS


def test_unresolved_draft_reaches_human_interrupt_with_approve_available(
    synthetic_corpus, monkeypatch
):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "poison"}}
    graph.invoke(
        {
            "idea": "I reduced routing time by 41%.",
            "thread_id": "poison",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )
    snapshot = graph.get_state(run_config)
    state = snapshot.values
    assert state["gate_verdict"] == "warn"
    assert snapshot.next == ("hitl",)
    assert "approve" in snapshot.tasks[0].interrupts[0].value["actions"]
    assert not state.get("terminal_reason")


def test_unresolved_draft_can_be_saved_without_an_acknowledgement_gate(
    synthetic_corpus, monkeypatch
):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    committed: list[dict] = []
    monkeypatch.setattr(graph_module, "commit", lambda state: committed.append(state) or {})
    graph = graph_module.build_graph()
    run_config = {"configurable": {"thread_id": "blocked-approval"}}
    graph.invoke(
        {
            "idea": "I reduced routing time by 41%.",
            "thread_id": "blocked-approval",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )

    graph.invoke(Command(resume={"action": "approve"}), config=run_config)

    state = graph.get_state(run_config).values
    assert committed and committed[0]["decision"] == "approve"
    assert state["decision"] == "approve"


def test_human_can_edit_unresolved_draft_then_approve_clean_revision(
    synthetic_corpus, monkeypatch, tmp_path
):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "blocked-edit"}}
    graph.invoke(
        {
            "idea": "I reduced routing time by 41%.",
            "thread_id": "blocked-edit",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )

    graph.invoke(
        Command(
            resume={
                "action": "edit",
                "draft": "I reduced routing time by 30% by treating labels as product decisions.",
            }
        ),
        config=run_config,
    )

    snapshot = graph.get_state(run_config)
    assert snapshot.values["gate_verdict"] == "pass"
    assert snapshot.next == ("hitl",)
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "PRIVATE", tmp_path / "private")

    graph.invoke(Command(resume={"action": "approve"}), config=run_config)

    state = graph.get_state(run_config).values
    assert state["queue_path"].startswith("drafts/queue/")
    assert (tmp_path / state["queue_path"]).exists()


def test_human_source_clears_the_matching_unresolved_claim(
    synthetic_corpus, monkeypatch, tmp_path
):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    truth_table = tmp_path / "private" / "identity" / "truth-table.md"
    truth_table.parent.mkdir(parents=True)
    truth_table.write_text(
        (synthetic_corpus / "private" / "identity" / "truth-table.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (truth_table.parent / "voice.md").write_text(
        (synthetic_corpus / "private" / "identity" / "voice.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(common, "PRIVATE", tmp_path / "private")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "source"}}
    graph.invoke(
        {
            "idea": "I reduced routing time by 41%.",
            "thread_id": "source",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )

    graph.invoke(
        Command(
            resume={
                "action": "source",
                "claim": "41%",
                "proof": "Reviewer-entered dashboard export",
                "date": "2026-08-30",
                "verified": "yes",
            }
        ),
        config=run_config,
    )

    state = graph.get_state(run_config).values
    assert state["claims_report"]["unresolved"] == []
    assert state["claims_report"]["unmatched"] == []


def test_approving_unresolved_claims_records_spans_without_an_acknowledgement_gate(
    synthetic_corpus, monkeypatch, tmp_path
):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "acknowledged-unresolved"}}
    graph.invoke(
        {
            "idea": "I reduced routing time by 41%.",
            "thread_id": "acknowledged-unresolved",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "PRIVATE", tmp_path / "private")

    graph.invoke(
        Command(resume={"action": "approve"}), config=run_config
    )

    state = graph.get_state(run_config).values
    queued = tmp_path / state["queue_path"]
    queued_text = queued.read_text(encoding="utf-8")
    assert 'unresolved_claim_spans: ["41%"]' in queued_text


def test_out_of_scope_request_still_reaches_a_draft(synthetic_corpus, monkeypatch):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "fallback"}}
    graph.invoke(
        {"idea": "book me a flight", "thread_id": "fallback", "revision": 0}, config=run_config
    )
    state = graph.get_state(run_config).values
    assert state["intent"] == "out_of_scope"
    assert state["draft"]
    assert graph.get_state(run_config).next == ("hitl",)


def test_empty_index_degrades_but_still_reaches_a_draft(synthetic_corpus, monkeypatch):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    monkeypatch.setenv("FAULT_EMPTY_INDEX", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "empty-index"}}
    graph.invoke(
        {
            "idea": "A grounded product lesson.",
            "thread_id": "empty-index",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )
    state = graph.get_state(run_config).values
    assert state["draft"]
    assert any("No grounded stories" in reason for reason in state["degradation_reasons"])
    assert graph.get_state(run_config).next == ("hitl",)


def test_transient_search_fault_retries_and_still_reaches_a_draft(synthetic_corpus, monkeypatch):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    monkeypatch.setenv("FAULT_SEARCH_500", "1")
    monkeypatch.setattr(config, "RETRY_BASE_DELAY", 0)
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "search-500"}}
    graph.invoke(
        {
            "idea": "A grounded product lesson.",
            "thread_id": "search-500",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )
    state = graph.get_state(run_config).values
    assert any(error["class"] == "transient" for error in state["errors"])
    assert state["draft"]
    assert graph.get_state(run_config).next == ("hitl",)


def test_forced_ungrounded_fault_hits_integrity_gate(synthetic_corpus, monkeypatch):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    monkeypatch.setenv("FAULT_FORCE_UNGROUNDED", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "forced-ungrounded"}}
    graph.invoke(
        {
            "idea": "A grounded product lesson.",
            "thread_id": "forced-ungrounded",
            "forced_intent": "authority",
            "revision": 0,
        },
        config=run_config,
    )
    snapshot = graph.get_state(run_config)
    state = snapshot.values
    assert state["gate_verdict"] == "warn"
    assert snapshot.next == ("hitl",)
    assert state["claims_report"]["unresolved"]
