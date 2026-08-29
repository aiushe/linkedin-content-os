from langgraph.types import Command

from agent import config
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


def test_ungrounded_metric_hard_stops(synthetic_corpus, monkeypatch):
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
    state = graph.get_state(run_config).values
    assert state["gate_verdict"] == "block"
    assert "Integrity stop" in state["terminal_reason"]


def test_out_of_scope_request_falls_back(synthetic_corpus, monkeypatch):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    graph = build_graph()
    run_config = {"configurable": {"thread_id": "fallback"}}
    graph.invoke(
        {"idea": "book me a flight", "thread_id": "fallback", "revision": 0}, config=run_config
    )
    state = graph.get_state(run_config).values
    assert state["intent"] == "out_of_scope"
    assert "Out of scope" in state["terminal_reason"]


def test_empty_index_escalates_as_capability_failure(synthetic_corpus, monkeypatch):
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
    assert any(error["class"] == "capability" for error in state["errors"])
    assert state["terminal_reason"].startswith("Capability failure")


def test_transient_search_fault_retries_then_escalates(synthetic_corpus, monkeypatch):
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
    assert state["terminal_reason"].startswith("Capability failure")


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
    state = graph.get_state(run_config).values
    assert state["gate_verdict"] == "block"
    assert "Integrity stop" in state["terminal_reason"]
