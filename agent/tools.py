"""Read-only LangChain tools and direct wrappers used by grounding."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from typing import Any

from langchain_core.tools import tool

from pipeline import claims

from .errors import AgentFailure, FailureClass, with_retry
from .mcp_loader import server as content_mcp


def _call_mcp(candidate: Any, **kwargs: Any) -> Any:
    """Call a FastMCP-decorated function across supported FastMCP versions."""

    function = getattr(candidate, "fn", candidate)
    return function(**kwargs)


def search_stories_read(query: str, *, k: int = 5) -> list[dict[str, Any]]:
    if os.getenv("FAULT_SEARCH_500"):
        raise AgentFailure(FailureClass.TRANSIENT, "Injected story-search 500")
    if os.getenv("FAULT_SLOW_TOOL"):
        time.sleep(0.05)
    if os.getenv("FAULT_EMPTY_INDEX"):
        return []
    return _call_mcp(content_mcp.search_stories, query=query, k=k)


def get_allowlist_read() -> list[dict[str, Any]]:
    return [asdict(fact) for fact in claims.load_allowlist()]


def find_viral_posts_read(topic: str, *, k: int = 5) -> list[dict[str, Any]]:
    return _call_mcp(content_mcp.find_viral_posts, topic=topic, k=k)


def get_template_read(template_id: int) -> dict[str, Any] | None:
    result = _call_mcp(content_mcp.get_template, template_id=template_id)
    return result if result.get("examples") else None


def web_search_read(query: str) -> list[dict[str, str]]:
    """Null-provider network tool: safe by default until a provider is configured."""

    provider = os.getenv("WEB_SEARCH_PROVIDER", "").lower()
    if not provider:
        return []
    raise AgentFailure(
        FailureClass.CAPABILITY,
        f"WEB_SEARCH_PROVIDER={provider!r} is not configured by this local harness.",
    )


@tool
def search_stories(query: str) -> str:
    """Read grounded story records. Never drafts or writes content."""

    return json.dumps(search_stories_read(query), default=str)


@tool
def get_allowlist() -> str:
    """Read the verified numeric and factual allowlist."""

    return json.dumps(get_allowlist_read(), default=str)


@tool
def find_viral_posts(topic: str) -> str:
    """Read local high-performing market posts when intel is available."""

    return json.dumps(find_viral_posts_read(topic), default=str)


@tool
def get_template(template_id: int) -> str:
    """Read a market-template skeleton by ID; never creates a draft."""

    return json.dumps(get_template_read(template_id), default=str)


@tool
def web_search(query: str) -> str:
    """Read optional web context through a separately configured provider."""

    return json.dumps(web_search_read(query), default=str)


def get_read_tools() -> list[Any]:
    """Return the only tools a grounding ReAct agent may receive.

    Deliberately excludes queue_draft: writing is structurally impossible from a
    model tool call and occurs only in the graph's human-gated commit node.
    """

    return [search_stories, get_allowlist, find_viral_posts, get_template, web_search]


def retrying_story_search(query: str) -> list[dict[str, Any]]:
    return with_retry(lambda: search_stories_read(query))
