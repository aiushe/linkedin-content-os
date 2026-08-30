"""Mem0 profile memory stays scoped, user-approved, and outside factual grounding."""

from __future__ import annotations

import pytest

from agent import config, memory
from agent.nodes import memory as memory_node
from agent.nodes import write


class FakeTransport:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeMemoryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, dict]] = []

    def search(self, query: str, **kwargs):
        self.calls.append(("search", query, kwargs))
        return {
            "results": [
                {"id": "memory-1", "memory": "Prefers concrete product lessons."},
                {"id": "memory-2", "memory": "Targets operator roles."},
            ]
        }

    def get_all(self, **kwargs):
        self.calls.append(("get_all", None, kwargs))
        return {"results": [{"id": "memory-1", "memory": "A saved preference."}]}

    def add(self, messages, **kwargs):
        self.calls.append(("add", messages, kwargs))
        return {"results": []}

    def update(self, memory_id: str, **kwargs):
        self.calls.append(("update", memory_id, kwargs))
        return {"id": memory_id}

    def delete(self, memory_id: str):
        self.calls.append(("delete", memory_id, {}))
        return {"id": memory_id}


def _fake_service(monkeypatch) -> tuple[FakeMemoryClient, FakeTransport]:
    client = FakeMemoryClient()
    transport = FakeTransport()
    monkeypatch.setattr(memory, "_memory_client", lambda: (client, transport))
    return client, transport


def test_recall_uses_static_query_and_scoped_user(monkeypatch):
    client, transport = _fake_service(monkeypatch)
    monkeypatch.setattr(config, "MEM0_USER_ID", "opaque-profile-scope")
    monkeypatch.setattr(config, "MEM0_TOP_K", 1)

    records = memory.recall_profile_memories()

    assert records == [
        {
            "id": "memory-1",
            "memory": "Prefers concrete product lessons.",
            "created_at": "",
            "updated_at": "",
        }
    ]
    assert client.calls == [
        (
            "search",
            memory.PROFILE_MEMORY_QUERY,
            {"filters": {"user_id": "opaque-profile-scope"}, "top_k": 1},
        )
    ]
    assert transport.closed


def test_memory_write_requires_explicit_approval_and_screens_sensitive_input(monkeypatch):
    client, _ = _fake_service(monkeypatch)

    with pytest.raises(memory.ProfileMemoryError, match="approval checkbox"):
        memory.remember_profile_fact("I prefer direct writing.", approved=False)
    with pytest.raises(memory.ProfileMemoryError, match="credentials"):
        memory.remember_profile_fact("My API key is sk_1234567890abcdefghijkl", approved=True)
    with pytest.raises(memory.ProfileMemoryError, match="credentials"):
        memory.remember_profile_fact("Contact me at person@example.com", approved=True)

    memory.remember_profile_fact("I prefer direct writing.", approved=True)

    assert client.calls == [
        (
            "add",
            [{"role": "user", "content": "I prefer direct writing."}],
            {
                "user_id": config.MEM0_USER_ID,
                "metadata": {"source": "explicit-user-approval", "kind": "profile-memory"},
            },
        )
    ]


def test_memory_management_operations_are_user_scoped_and_approved(monkeypatch):
    client, _ = _fake_service(monkeypatch)

    assert memory.list_profile_memories()[0]["memory"] == "A saved preference."
    memory.update_profile_memory("memory-1", "I prefer concise hooks.", approved=True)
    with pytest.raises(memory.ProfileMemoryError, match="deletion approval"):
        memory.delete_profile_memory("memory-1", approved=False)
    memory.delete_profile_memory("memory-1", approved=True)

    assert client.calls == [
        ("get_all", None, {"filters": {"user_id": config.MEM0_USER_ID}, "page_size": 50}),
        ("update", "memory-1", {"text": "I prefer concise hooks."}),
        ("delete", "memory-1", {}),
    ]


def test_memory_node_withholds_context_from_langsmith_without_second_approval(monkeypatch):
    monkeypatch.setattr(config, "mem0_service_enabled", lambda: True)
    monkeypatch.setattr(config, "mem0_prompt_enabled", lambda: False)

    result = memory_node.recall_profile_memory({"idea": "A private raw draft idea."})

    assert result["profile_memory"] == []
    assert result["profile_memory_status"] == "withheld_for_langsmith_tracing"
    assert result["degradation_reasons"]


def test_mem0_enabled_false_disables_memory_before_any_client_call(monkeypatch):
    monkeypatch.setattr(config, "MEM0_ENABLED", False)
    monkeypatch.setattr(config, "MEM0_API_KEY", "configured-for-test")
    monkeypatch.setattr(
        memory, "recall_profile_memories", lambda: pytest.fail("must not call Mem0")
    )

    result = memory_node.recall_profile_memory({})

    assert result == {"profile_memory": [], "profile_memory_status": "disabled"}


@pytest.mark.parametrize(
    ("tracing", "expected"),
    [("true", False), ("false", True)],
)
def test_mem0_prompt_privacy_guard_changes_only_with_langsmith_tracing(
    monkeypatch, tracing, expected
):
    """Tracing, not pytest logging, controls whether profile memory reaches prompts."""

    monkeypatch.setattr(config, "mem0_service_enabled", lambda: True)
    monkeypatch.setattr(config, "MEM0_ALLOW_LANGSMITH_TRACING", False)
    monkeypatch.setenv("LANGSMITH_TRACING", tracing)

    assert config.mem0_prompt_enabled() is expected


def test_memory_node_degrades_without_widening_grounding(monkeypatch):
    monkeypatch.setattr(config, "mem0_service_enabled", lambda: True)
    monkeypatch.setattr(config, "mem0_prompt_enabled", lambda: True)
    monkeypatch.setattr(
        memory,
        "recall_profile_memories",
        lambda: (_ for _ in ()).throw(memory.ProfileMemoryError("unavailable")),
    )

    result = memory_node.recall_profile_memory({})

    assert result["profile_memory"] == []
    assert result["profile_memory_status"] == "unavailable"
    assert result["errors"][0]["class"] == "degradable"


def test_writer_labels_memory_as_non_evidentiary(monkeypatch, tmp_path):
    voice_rules = tmp_path / "voice.md"
    voice_rules.write_text("Use a direct voice.", encoding="utf-8")
    monkeypatch.setattr(write.voice, "identity_file", lambda _: voice_rules)

    prompt = write._prompt(
        {
            "idea": "Draft a grounded lesson.",
            "profile_memory": [{"id": "memory-1", "memory": "Prefers concise hooks."}],
        }
    )

    assert "Non-evidentiary personal memory" in prompt
    assert "cannot supplement the verified allowlist" in prompt
    assert "Prefers concise hooks." in prompt
