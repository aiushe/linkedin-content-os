"""Live market intel via the hosted Apify MCP server, under strict cost control.

Two tiers of market evidence exist and must never be confused:

* **Scored** — the batch watchlist pull (``scrape`` -> ``normalize`` -> ``xfactor``).
  ``xfactor.py`` needs >= 10 posts per author for a self-excluded baseline, so only a
  bulk per-author pull can yield an x-factor.
* **Unscored** — this module. A keyword search returns one post per author with no
  history, so ``x_factor`` is structurally always ``None``.

Unscored posts show what is timely. They may inform structure and topic. They may never
justify a factual claim, and must never be ranked by raw likes as though that were an
x-factor: replacing that signal is the entire reason x-factor exists.

Cost controls, in order of leverage:
  1. Intent gate      - only intents in ``config.INTEL_ENABLED_INTENTS`` may spend.
  2. Once per run     - the caller stores the result in state; never re-fetch in the
                        revision loop, where only voice and claims change.
  3. Disk cache + TTL - identical query within the TTL costs $0. Makes demo takes and
                        eval reruns free.
  4. Deterministic compression - ``compress()`` is pure Python. Only the top-K hooks and
                        skeletons ever reach a model context, never full post bodies.
                        This is ~50x cheaper than passing raw results through.
  5. Fixed arguments  - the caller derives the query; this is not a free-form ReAct tool
                        the model can invoke repeatedly with new phrasings.
  6. Accounting       - every call reports ``estimated_usd`` for the cost table.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from pipeline import voice
from pipeline.common import INTEL, first_lines

from . import config

APIFY_MCP_URL = "https://mcp.apify.com/"
SEARCH_ACTOR = "harvestapi/linkedin-post-search"


def available() -> tuple[bool, str]:
    """Report whether a live intel call is possible, without raising."""

    if not os.getenv("APIFY_API_TOKEN"):
        return False, "APIFY_API_TOKEN is not set; live market intel is unavailable."
    if os.getenv("AGENT_OFFLINE", "").lower() in {"1", "true", "yes"}:
        return False, "AGENT_OFFLINE is set; skipping live market intel."
    return True, ""


def should_fetch(intent: str) -> bool:
    """Control 1: only spend on intents that actually benefit from timeliness."""

    return intent in config.INTEL_ENABLED_INTENTS


def _cache_path(query: str, posted_limit: str) -> Path:
    key = hashlib.sha256(f"{query.strip().lower()}|{posted_limit}".encode()).hexdigest()[:16]
    return INTEL / "cache" / f"search-{key}.json"


def _read_cache(path: Path) -> dict[str, Any] | None:
    """Control 3: a hit inside the TTL costs nothing."""

    if not path.exists():
        return None
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours > config.INTEL_CACHE_TTL_HOURS:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    payload["cached"] = True
    payload["estimated_usd"] = 0.0
    return payload


def compress(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Control 4: pure-Python reduction. No LLM, no full post bodies.

    Twenty-five posts of raw text is roughly 7,000 tokens. The writer needs structure,
    not prose, so keep the top-K hooks and shapes and discard everything else. The
    result is a few hundred tokens.
    """

    ranked = sorted(
        posts,
        key=lambda item: int(item.get("likes") or 0) + 3 * int(item.get("comments") or 0),
        reverse=True,
    )
    return [
        {
            "hook": first_lines(post.get("text") or "", 2)[: config.INTEL_HOOK_CHARS],
            "word_count": len((post.get("text") or "").split()),
            "paragraphs": len([p for p in (post.get("text") or "").split("\n\n") if p.strip()]),
            "likes": int(post.get("likes") or 0),
            "comments": int(post.get("comments") or 0),
            "post_url": post.get("post_url"),
            "x_factor": None,
            "scored": False,
        }
        for post in ranked[: config.INTEL_TOP_K]
    ]


def structural_summaries(posts: list[dict[str, Any]]) -> list[dict[str, int | str]]:
    """Retain all-results shape signals without retaining any additional prose.

    The market brief needs a median across the complete actor result, not merely the
    five human exemplars. These scalar summaries never reach the writer as examples.
    """

    summaries: list[dict[str, int | str]] = []
    for post in posts:
        text = str(post.get("text") or "")
        summaries.append(
            {
                "word_count": len(text.split()),
                "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
                "opening_move": str(voice.feature_set(text).get("opening_move", "scene_or_claim")),
            }
        )
    return summaries


async def _fetch(query: str, posted_limit: str, max_posts: int) -> list[dict[str, Any]]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            "apify": {
                "transport": "streamable_http",
                "url": f"{APIFY_MCP_URL}?actors={SEARCH_ACTOR}",
                "headers": {"Authorization": f"Bearer {os.environ['APIFY_API_TOKEN']}"},
            }
        }
    )
    tools = await client.get_tools()
    if not tools:
        return []
    caller = next((tool for tool in tools if "search" in tool.name.lower()), tools[0])
    raw = await caller.ainvoke(
        {"searchQueries": [query], "postedLimit": posted_limit, "maxPosts": max_posts}
    )
    return raw if isinstance(raw, list) else [raw]


async def _bounded_fetch(query: str, posted_limit: str, max_posts: int) -> list[dict[str, Any]]:
    """Create the network coroutine only when the bounded runner actually starts it."""

    return await asyncio.wait_for(
        _fetch(query, posted_limit, max_posts), timeout=config.INTEL_TIMEOUT_SECONDS
    )


def _normalize(records: list[Any]) -> list[dict[str, Any]]:
    posts = []
    for record in records:
        if not isinstance(record, dict):
            continue
        author = record.get("author")
        posts.append(
            {
                "text": record.get("content") or record.get("text") or "",
                "author_name": author.get("name")
                if isinstance(author, dict)
                else record.get("authorName"),
                "post_url": record.get("linkedinUrl") or record.get("url"),
                "posted_at": record.get("postedAt") or record.get("postedDate"),
                "likes": record.get("likes") or record.get("reactions") or 0,
                "comments": record.get("comments") or 0,
            }
        )
    return posts


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "posts": [],
        "scored": False,
        "cached": False,
        "estimated_usd": 0.0,
    }


def search_trending_posts(
    query: str,
    posted_limit: str = "week",
    max_posts: int | None = None,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Fetch timely posts for one topic. Always DEGRADABLE: never raises to the graph."""

    max_posts = min(max_posts or config.INTEL_MAX_POSTS, config.INTEL_MAX_POSTS)
    ok, reason = available()
    path = _cache_path(query, posted_limit)
    if use_cache:
        hit = _read_cache(path)
        if hit is not None:
            return hit
    if not ok:
        return _unavailable(reason)
    fetch = _bounded_fetch(query, posted_limit, max_posts)
    try:
        records = asyncio.run(fetch)
    except (TimeoutError, asyncio.TimeoutError):
        fetch.close()
        return _unavailable(
            f"Live intel timed out after {config.INTEL_TIMEOUT_SECONDS:g}s; continuing without it."
        )
    except Exception as exc:  # network, auth, rate limit, actor failure
        # A monkeypatched event-loop seam can fail before consuming the coroutine.
        # Closing it avoids a noisy unawaited-coroutine warning in that degradable path.
        fetch.close()
        return _unavailable(
            f"Live intel unavailable ({type(exc).__name__}); continuing without it."
        )
    posts = _normalize(records)
    payload = {
        "available": True,
        "reason": "",
        "posts": compress(posts),
        "structural_posts": structural_summaries(posts),
        "scored": False,
        "cached": False,
        "fetched_count": len(posts),
        "estimated_usd": round(len(posts) * config.INTEL_USD_PER_POST, 5),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass
    return payload
