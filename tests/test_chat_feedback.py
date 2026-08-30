from agent.nodes.hitl import hitl
from agent.nodes.write import _prompt, write


def test_feedback_becomes_a_persistent_user_direction(monkeypatch):
    monkeypatch.setattr(
        "agent.nodes.hitl.interrupt",
        lambda _payload: {"action": "feedback", "feedback": "Make the opening more direct."},
    )

    update = hitl({"revision": 1, "critique": {"targeted_fixes": ["Keep the metric."]}})

    assert update["decision"] == "feedback"
    assert update["revision"] == 2
    assert update["user_directions"] == ["Make the opening more direct."]
    assert "critique" not in update


def test_user_direction_is_in_the_writer_prompt_and_changes_the_next_draft(
    synthetic_corpus, monkeypatch
):
    monkeypatch.setenv("AGENT_OFFLINE", "1")
    first_state = {
        "idea": "Write a post about treating labels as product decisions.",
        "allowlist": [],
        "stories": [],
        "intent": "authority",
        "revision": 0,
    }
    first_draft = write(first_state)["draft"]
    direction = "Make the opening more direct."
    revision_state = {
        **first_state,
        "draft": first_draft,
        "revision": 1,
        "user_directions": [direction],
    }

    assert direction in _prompt(revision_state)
    revised_draft = write(revision_state)["draft"]
    assert revised_draft != first_draft
    assert direction in revised_draft


def test_writer_prompt_keeps_prior_directions_and_the_previous_draft(synthetic_corpus):
    state = {
        "idea": "A product lesson.",
        "draft": "First version.",
        "user_directions": ["Open with the tension.", "Use shorter paragraphs."],
        "allowlist": [],
        "stories": [],
        "intent": "authority",
    }

    prompt = _prompt(state)

    assert "First version." in prompt
    assert "Open with the tension." in prompt
    assert "Use shorter paragraphs." in prompt
