"""Narrow Mem0 Platform adapter for user-approved personal profile memory.

This module never reads the local private corpus and never records a draft or a raw chat. The
only write path accepts one fact typed and explicitly approved by the human in the Streamlit
surface. Retrieved memories are deliberately non-evidentiary context: deterministic grounding
remains the only source of factual claims.
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable, TypeVar

# Mem0's Python SDK otherwise enables PostHog telemetry by default. The application sends memory
# operations only to the explicitly approved Mem0 Platform project, not an additional analytics
# service. A caller may still explicitly override this before the process starts.
os.environ.setdefault("MEM0_TELEMETRY", "false")

import httpx
from mem0 import MemoryClient

from . import config

PROFILE_MEMORY_QUERY = (
    "Profile background, career themes, writing preferences, and LinkedIn goals relevant to "
    "grounded content drafting."
)
MAX_MEMORY_CHARS = 600
_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b(api[ _-]?key|password|secret|access[ _-]?token)\b"),
    re.compile(r"(?i)\b(?:sk|pk|rk)_[a-z0-9_-]{16,}\b"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"https?://|www\.", re.IGNORECASE),
)
_MEMORY_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
T = TypeVar("T")


class ProfileMemoryError(RuntimeError):
    """Raised with a safe, user-facing message for Mem0 failures."""


def _memory_client() -> tuple[MemoryClient, httpx.Client]:
    if not config.mem0_service_enabled():
        raise ProfileMemoryError("Profile memory is not configured for this run.")
    transport = httpx.Client(timeout=config.MEM0_TIMEOUT_SECONDS)
    try:
        return MemoryClient(api_key=config.MEM0_API_KEY, client=transport), transport
    except Exception as exc:
        transport.close()
        raise ProfileMemoryError("Mem0 profile memory is unavailable.") from exc


def _call(operation: Callable[[MemoryClient], T]) -> T:
    client, transport = _memory_client()
    try:
        return operation(client)
    except ProfileMemoryError:
        raise
    except Exception as exc:
        raise ProfileMemoryError("Mem0 profile memory is unavailable.") from exc
    finally:
        transport.close()


def _records(payload: Any, *, limit: int | None = None) -> list[dict[str, str]]:
    values = payload.get("results", []) if isinstance(payload, dict) else []
    if not isinstance(values, list):
        return []
    records: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        text = str(item.get("memory") or item.get("text") or "").strip()
        memory_id = str(item.get("id") or "").strip()
        if text and memory_id:
            records.append(
                {
                    "id": memory_id,
                    "memory": text,
                    "created_at": str(item.get("created_at") or ""),
                    "updated_at": str(item.get("updated_at") or ""),
                }
            )
    return records[:limit] if limit is not None else records


def _approved_text(text: str, *, approved: bool) -> str:
    if not approved:
        raise ProfileMemoryError("Select the approval checkbox before sending a memory to Mem0.")
    value = " ".join(text.split())
    if not value:
        raise ProfileMemoryError("Enter a profile fact or preference before saving it.")
    if len(value) > MAX_MEMORY_CHARS:
        raise ProfileMemoryError(f"Profile memory is limited to {MAX_MEMORY_CHARS} characters.")
    if any(pattern.search(value) for pattern in _SENSITIVE_PATTERNS):
        raise ProfileMemoryError(
            "Do not store credentials, contact details, or URLs in profile memory."
        )
    return value


def _approved_memory_id(memory_id: str) -> str:
    value = str(memory_id).strip()
    if not _MEMORY_ID.fullmatch(value):
        raise ProfileMemoryError("The selected memory identifier is invalid.")
    return value


def recall_profile_memories() -> list[dict[str, str]]:
    """Retrieve static, user-scoped context without sending a raw draft idea to Mem0."""

    payload = _call(
        lambda client: client.search(
            PROFILE_MEMORY_QUERY,
            filters={"user_id": config.MEM0_USER_ID},
            top_k=config.MEM0_TOP_K,
        )
    )
    return _records(payload, limit=config.MEM0_TOP_K)


def list_profile_memories() -> list[dict[str, str]]:
    """List user-scoped memories for the explicit Streamlit management surface."""

    payload = _call(
        lambda client: client.get_all(
            filters={"user_id": config.MEM0_USER_ID}, page_size=50
        )
    )
    return _records(payload)


def remember_profile_fact(text: str, *, approved: bool) -> None:
    """Store exactly one human-approved, minimally screened profile memory."""

    value = _approved_text(text, approved=approved)
    _call(
        lambda client: client.add(
            [{"role": "user", "content": value}],
            user_id=config.MEM0_USER_ID,
            metadata={"source": "explicit-user-approval", "kind": "profile-memory"},
        )
    )


def update_profile_memory(memory_id: str, text: str, *, approved: bool) -> None:
    """Replace one memory only after an explicit approval of the new text."""

    value = _approved_text(text, approved=approved)
    selected_id = _approved_memory_id(memory_id)
    _call(lambda client: client.update(selected_id, text=value))


def delete_profile_memory(memory_id: str, *, approved: bool) -> None:
    """Permanently delete the exact human-selected memory."""

    if not approved:
        raise ProfileMemoryError("Select the deletion approval checkbox first.")
    selected_id = _approved_memory_id(memory_id)
    _call(lambda client: client.delete(selected_id))
