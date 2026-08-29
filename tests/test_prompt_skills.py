"""Writer and critic prompts use the authored skill files selected by intent."""

from __future__ import annotations

from agent import skills
from agent.nodes import critique, write


def _write_authority_skill(root, body: str) -> None:
    path = root / "authority-post" / "SKILL.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        "---\nname: authority-post\ndescription: test\n---\n\n" + body,
        encoding="utf-8",
    )


def test_skill_file_edits_change_writer_and_critic_prompts(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    voice_rules = tmp_path / "voice.md"
    voice_rules.write_text("voice rules", encoding="utf-8")
    monkeypatch.setattr(write.voice, "identity_file", lambda _: voice_rules)
    state = {"intent": "authority", "idea": "A grounded idea."}

    _write_authority_skill(tmp_path, "FIRST AUTHORISED PLAYBOOK MARKER")
    assert "FIRST AUTHORISED PLAYBOOK MARKER" in write._prompt(state)
    assert "FIRST AUTHORISED PLAYBOOK MARKER" in critique._prompt(state)

    _write_authority_skill(tmp_path, "SECOND AUTHORISED PLAYBOOK MARKER")
    assert "SECOND AUTHORISED PLAYBOOK MARKER" in write._prompt(state)
    assert "SECOND AUTHORISED PLAYBOOK MARKER" in critique._prompt(state)


def test_comment_prompt_forbids_invented_recipient_placeholders(monkeypatch, tmp_path) -> None:
    voice_rules = tmp_path / "voice.md"
    voice_rules.write_text("voice rules", encoding="utf-8")
    monkeypatch.setattr(write.voice, "identity_file", lambda _: voice_rules)

    prompt = write._prompt({"intent": "comment", "idea": "Reply to this post."})

    assert "Hard comment safety constraint" in prompt
    assert "Do not invent a name, greeting, or bracketed placeholder" in prompt
    assert "Do not use ordinal or superlative framing" in prompt
    assert prompt.endswith("verbatim in the verified allowlist.")


def test_comment_safety_constraint_follows_conflicting_playbook(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    playbook = tmp_path / "comment-drafter" / "SKILL.md"
    playbook.parent.mkdir()
    playbook.write_text("Draft comments using first name only.", encoding="utf-8")
    voice_rules = tmp_path / "voice.md"
    voice_rules.write_text("voice rules", encoding="utf-8")
    monkeypatch.setattr(write.voice, "identity_file", lambda _: voice_rules)

    prompt = write._prompt({"intent": "comment", "idea": "Reply to this post."})

    assert prompt.index("Draft comments using first name only.") < prompt.index(
        "Hard comment safety constraint"
    )
