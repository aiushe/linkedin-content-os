"""Turn unscored live-search results into safe market-shape guidance.

This module deliberately has no path to the factual allowlist.  It can describe the
current market's *shape* (length, opening move, saturated angles, vocabulary), but
never supplies evidence for a claim or text for the writer to imitate.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from statistics import median
from typing import Any

from pydantic import BaseModel, Field

from pipeline import voice

from . import config, intel_mcp
from .models import CostMeter, invoke_with_deadline

OPENING_MOVES = ("scene_or_claim", "question", "number")
WORD_RE = re.compile(r"[a-z0-9][a-z0-9'-]*", re.IGNORECASE)
BOOLEAN_OPERATOR_RE = re.compile(r"\b(?:AND|OR|NOT)\b", re.IGNORECASE)
STOPWORDS = frozenset(
    {
        "a",
        "about",
        "after",
        "again",
        "all",
        "also",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "being",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "get",
        "had",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "like",
        "make",
        "more",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "out",
        "post",
        "posts",
        "should",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "use",
        "using",
        "was",
        "we",
        "what",
        "when",
        "which",
        "who",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)


@dataclass(frozen=True)
class MarketBrief:
    """A compact, unscored constraint set for a single draft run."""

    available: bool
    reason: str
    topic: str
    window: str
    post_count: int
    topic_alive: bool
    median_word_count: int
    median_paragraphs: int
    hook_moves: dict[str, int]
    fingerprint_hook_moves: dict[str, int]
    hook_alignment: str
    saturated_angles: list[str]
    open_angles: list[str]
    current_vocabulary: list[str]
    exemplars: list[dict[str, Any]]
    scored: bool = False
    cached: bool = False
    estimated_usd: float = 0.0
    actor_estimated_usd: float = 0.0
    saturation_estimated_usd: float = 0.0


class SaturationOutput(BaseModel):
    """Small, bounded response from the optional angle-classification call."""

    saturated_angles: list[str] = Field(default_factory=list, max_length=4)
    open_angles: list[str] = Field(default_factory=list, max_length=4)


def should_fetch(intent: str) -> bool:
    """Expose the intent gate alongside the brief API."""

    return intel_mcp.should_fetch(intent)


def _terms(value: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(value) if token.lower() not in STOPWORDS]


def derive_query(idea: str, pillar: str | None = None) -> str:
    """Build a stable actor-safe query without an LLM-generated cache miss.

    The actor accepts at most 500 characters and five boolean operators.  This function
    does not introduce boolean syntax, but strips any excess supplied in an idea as a
    defence-in-depth measure.
    """

    pillar_terms = _terms(pillar or "")[:6]
    idea_terms = _terms(idea)
    terms: list[str] = []
    for term in [*pillar_terms, *idea_terms]:
        if term not in terms:
            terms.append(term)
    query = " ".join(terms) or "linkedin product work"
    query = " ".join(query.split())[:500].strip()
    operators = list(BOOLEAN_OPERATOR_RE.finditer(query))
    if len(operators) > 5:
        query = query[: operators[5].end()].strip()
    return query or "linkedin product work"


def _paragraph_count(post: dict[str, Any]) -> int:
    value = post.get("paragraphs")
    if isinstance(value, int):
        return max(value, 0)
    text = str(post.get("hook") or post.get("text") or "")
    return len([item for item in re.split(r"\n\s*\n", text) if item.strip()])


def _word_count(post: dict[str, Any]) -> int:
    value = post.get("word_count")
    if isinstance(value, int):
        return max(value, 0)
    return len(WORD_RE.findall(str(post.get("hook") or post.get("text") or "")))


def structural_stats(posts: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate shape signals only; no model call and no engagement ranking."""

    word_counts = [_word_count(post) for post in posts]
    paragraph_counts = [_paragraph_count(post) for post in posts]
    hook_moves = {move: 0 for move in OPENING_MOVES}
    for post in posts:
        opening = str(post.get("opening_move") or "")
        if not opening:
            opening = str(
                voice.feature_set(str(post.get("hook") or post.get("text") or "")).get(
                    "opening_move"
                )
            )
        if opening in hook_moves:
            hook_moves[opening] += 1
    return {
        "median_word_count": int(median(word_counts)) if word_counts else 0,
        "median_paragraphs": int(median(paragraph_counts)) if paragraph_counts else 0,
        "hook_moves": hook_moves,
    }


def _fingerprint_terms(profile: dict[str, Any]) -> set[str]:
    """Support a future lexical fingerprint without treating numeric features as words."""

    values: list[Any] = []
    for key in ("vocabulary", "terms", "lexicon"):
        value = profile.get(key, [])
        values.extend(value if isinstance(value, list) else [])
    return {term for value in values for term in _terms(str(value))}


def vocabulary(posts: list[dict[str, Any]], k: int = 8) -> list[str]:
    """Return novel high-frequency bigrams from compressed hooks, never full bodies."""

    try:
        known = _fingerprint_terms(voice.load_fingerprint())
    except Exception:
        known = set()
    counts: Counter[str] = Counter()
    for post in posts:
        tokens = _terms(str(post.get("hook") or post.get("text") or ""))
        for first, second in zip(tokens, tokens[1:]):
            if first in known or second in known:
                continue
            counts[f"{first} {second}"] += 1
    return [
        phrase
        for phrase, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:k]
    ]


def _clean_angles(values: list[str]) -> list[str]:
    """Bound model output before it is placed in state or a prompt."""

    result: list[str] = []
    for value in values:
        item = " ".join(str(value).split())[:120]
        if item and item not in result:
            result.append(item)
    return result[:4]


def saturation(hooks: list[str]) -> tuple[list[str], list[str]]:
    """Classify angle saturation from hooks only, degrading cleanly on every failure."""

    safe_hooks = [" ".join(str(hook).split())[: config.INTEL_HOOK_CHARS] for hook in hooks if hook]
    if not safe_hooks or not config.live_models_enabled():
        return [], []
    prompt = (
        "Classify LinkedIn post hooks for a writer seeking a differentiated angle. "
        "Return short topic labels only. Do not repeat wording, infer facts, or supply claims. "
        "Saturated angles are repeated themes in these hooks. Open angles are adjacent gaps "
        "suggested by what is absent, and may be empty.\n\nHooks:\n- "
        + "\n- ".join(safe_hooks[: config.INTEL_TOP_K])
    )
    try:
        from langchain_openai import ChatOpenAI

        meter = CostMeter(node="market_brief", model=config.MODEL_INTEL)
        output = invoke_with_deadline(
            lambda: ChatOpenAI(
                model=config.MODEL_INTEL, temperature=0, callbacks=[meter]
            )
            .with_structured_output(SaturationOutput)
            .invoke(prompt)
        )
        return _clean_angles(output.saturated_angles), _clean_angles(output.open_angles)
    except Exception:
        return [], []


def _hook_alignment(market: dict[str, int], fingerprint: dict[str, int]) -> str:
    if not any(market.values()) or not any(fingerprint.values()):
        return "unknown"
    market_lead = max(
        OPENING_MOVES, key=lambda move: (market.get(move, 0), -OPENING_MOVES.index(move))
    )
    return "consistent" if fingerprint.get(market_lead, 0) else "divergent"


def _exemplars(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep a human-inspectable hook and URL, never a post body."""

    return [
        {
            "hook": str(post.get("hook") or "")[: config.INTEL_HOOK_CHARS],
            "post_url": post.get("post_url"),
        }
        for post in posts[: config.INTEL_TOP_K]
    ]


def build(idea: str, intent: str, pillar: str | None = None) -> MarketBrief:
    """Fetch once and derive a market brief. This boundary is always degradable."""

    topic = derive_query(idea, pillar)
    window = config.INTEL_POSTED_LIMIT
    if not should_fetch(intent):
        return MarketBrief(
            available=False,
            reason=f"Market intel is not used for {intent!r} intent.",
            topic=topic,
            window=window,
            post_count=0,
            topic_alive=False,
            median_word_count=0,
            median_paragraphs=0,
            hook_moves={move: 0 for move in OPENING_MOVES},
            fingerprint_hook_moves={},
            hook_alignment="unknown",
            saturated_angles=[],
            open_angles=[],
            current_vocabulary=[],
            exemplars=[],
        )

    try:
        payload = intel_mcp.search_trending_posts(topic, posted_limit=window)
    except Exception as exc:  # Defensive: intel_mcp itself is intended never to raise.
        payload = {"available": False, "reason": f"Live intel unavailable ({type(exc).__name__})."}
    posts = [post for post in payload.get("posts", []) if isinstance(post, dict)]
    available = bool(payload.get("available"))
    try:
        profile = voice.load_fingerprint()
    except Exception:
        profile = {}
    fingerprint = {
        move: int(profile.get("opening_moves", {}).get(move, 0)) for move in OPENING_MOVES
    }
    structural_posts = payload.get("structural_posts", posts)
    stats = structural_stats(
        [post for post in structural_posts if isinstance(post, dict)]
        if isinstance(structural_posts, list)
        else posts
    )
    hooks = [str(post.get("hook") or "") for post in posts]
    saturated_angles, open_angles = saturation(hooks) if available else ([], [])
    post_count = int(payload.get("fetched_count") or len(posts))
    actor_usd = float(payload.get("estimated_usd") or 0.0)
    saturation_usd = (
        config.INTEL_SATURATION_ESTIMATED_USD
        if available and hooks and config.live_models_enabled()
        else 0.0
    )
    return MarketBrief(
        available=available,
        reason=str(payload.get("reason") or ""),
        topic=topic,
        window=window,
        post_count=post_count,
        topic_alive=post_count >= config.INTEL_MIN_ALIVE,
        median_word_count=stats["median_word_count"],
        median_paragraphs=stats["median_paragraphs"],
        hook_moves=stats["hook_moves"],
        fingerprint_hook_moves=fingerprint,
        hook_alignment=_hook_alignment(stats["hook_moves"], fingerprint),
        saturated_angles=saturated_angles,
        open_angles=open_angles,
        current_vocabulary=vocabulary(posts),
        exemplars=_exemplars(posts),
        scored=False,
        cached=bool(payload.get("cached")),
        estimated_usd=round(actor_usd + saturation_usd, 5),
        actor_estimated_usd=round(actor_usd, 5),
        saturation_estimated_usd=round(saturation_usd, 5),
    )


def render_prompt_block(brief: MarketBrief | dict[str, Any] | None) -> str:
    """Render constraints only. Examples and full post content never reach the writer."""

    if not brief:
        return ""
    if isinstance(brief, dict):
        try:
            brief = MarketBrief(**brief)
        except (TypeError, ValueError):
            return ""
    if not brief.available:
        return ""

    lines = [
        "MARKET CONTEXT — unscored. Timeliness signal only.",
        "Never a source of fact or phrasing.",
        f"- Topic active: {brief.post_count} posts in the last {brief.window}.",
        (
            f"- Posts landing here run ~{brief.median_word_count} words, "
            f"{brief.median_paragraphs} short paragraphs."
        ),
        (
            "- Hook moves: "
            + ", ".join(f"{brief.hook_moves.get(move, 0)} {move}" for move in OPENING_MOVES)
            + "."
        ),
    ]
    if brief.hook_alignment != "unknown":
        lines.append(
            f"  Your fingerprint is {brief.hook_alignment} with this opening pattern; "
            "make that a deliberate choice."
        )
    if brief.saturated_angles:
        lines.append(
            "- Saturated angles: "
            + ", ".join(f"“{angle}”" for angle in brief.saturated_angles)
            + ". Do NOT restate these. Find the gap."
        )
    if brief.open_angles:
        lines.append("- Open angles: " + ", ".join(brief.open_angles) + ".")
    if brief.current_vocabulary:
        lines.append("- Current vocabulary: " + ", ".join(brief.current_vocabulary) + ".")
    lines.extend(
        [
            "Use this for LENGTH, SHAPE, and ANGLE only.",
            "Do not borrow phrasing. Do not use it to support any claim.",
            "Numbers appearing above are other people's and are NOT in your allowlist.",
        ]
    )
    return "\n".join(lines)
