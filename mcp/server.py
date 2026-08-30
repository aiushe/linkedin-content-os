"""MCP surface for grounded, local content work.

Every read tool returns files the user can inspect. `log_story` is the only write tool and
always marks submitted metrics unverified until the truth table is updated with evidence.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.gates import safe_voice_score
from pipeline.claims import check as check_claims_report
from pipeline.common import (
    INTEL,
    content_hash,
    identity_file,
    load_all_posts,
    parse_datetime,
    private_stories_dir,
    read_json,
    slugify,
)
from pipeline.index_corpus import build_index
from pipeline.selfmetrics import my_posts

mcp = FastMCP("LinkedIn Content OS")


def story_index() -> List[Dict[str, Any]]:
    path = INTEL / "story-index.json"
    if not path.exists():
        build_index(path)
    return read_json(path, {"stories": []}).get("stories", [])


def terms(value: str) -> List[str]:
    return [
        word
        for word in re.findall(r"[a-z0-9]{3,}", value.lower())
        if word not in {"with", "from", "that", "this", "your", "about", "into"}
    ]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator else 0.0


@mcp.tool()
def search_stories(
    query: str,
    pillar: Optional[str] = None,
    stage: Optional[str] = None,
    must_have_metric: bool = False,
    k: int = 5,
) -> List[Dict[str, Any]]:
    """Retrieve grounded story records by metadata plus simple transparent lexical relevance."""
    query_terms = terms(query)
    results = []
    for story in story_index():
        pillars = [str(item).lower() for item in story.get("pillars", [])]
        if pillar and pillar.lower() not in pillars:
            continue
        if stage and story.get("stage") != stage:
            continue
        if must_have_metric and not story.get("has_verified_metric"):
            continue
        text = " ".join(
            str(story.get(key) or "")
            for key in ("title", "tension", "turn", "result", "lesson", "role_context")
        ).lower()
        score = sum(term in text for term in query_terms)
        results.append((score, story))
    results.sort(key=lambda item: (item[0], str(item[1].get("date") or "")), reverse=True)
    return [story for _, story in results[: max(1, min(k, 20))]]


@mcp.tool()
def get_truth_table() -> Dict[str, str]:
    """Return the raw claim allowlist; writers must use it before stating facts or metrics."""
    path = identity_file("truth-table.md")
    return {"path": str(path.relative_to(ROOT)), "content": path.read_text(encoding="utf-8")}


@mcp.tool()
def check_claims(draft_text: str) -> Dict[str, Any]:
    """Run the exact deterministic claim gate used by the LangGraph harness."""
    from dataclasses import asdict

    return asdict(check_claims_report(draft_text))


@mcp.tool()
def get_voice_report(draft_text: str) -> Dict[str, Any]:
    """Run the fail-closed deterministic voice gate used by the LangGraph harness."""
    return safe_voice_score(draft_text)


@mcp.tool()
def find_viral_posts(
    topic: Optional[str] = None,
    min_xfactor: float = 2.0,
    min_likes: int = 750,
    since: Optional[str] = None,
    k: int = 20,
) -> List[Dict[str, Any]]:
    """Find high-performing posts from the local normalized intel files."""
    since_date = parse_datetime(since) if since else None
    topic_terms = terms(topic or "")
    matches = []
    for post in load_all_posts():
        if int(post.get("likes") or 0) < min_likes:
            continue
        xfactor = post.get("x_factor")
        if not isinstance(xfactor, (int, float)) or xfactor < min_xfactor:
            continue
        posted = parse_datetime(post.get("posted_at"))
        if since_date and (not posted or posted < since_date):
            continue
        searchable = f"{post.get('text', '')} {post.get('hook', '')}".lower()
        if topic_terms and not all(term in searchable for term in topic_terms):
            continue
        matches.append(post)
    matches.sort(
        key=lambda item: (float(item.get("x_factor") or 0), int(item.get("engagement") or 0)),
        reverse=True,
    )
    return matches[: max(1, min(k, 100))]


@mcp.tool()
def get_template(template_id: int) -> Dict[str, Any]:
    """Return the top examples in a discovered text-template cluster and an inspectable skeleton."""
    matches = [post for post in load_all_posts() if post.get("template_id") == template_id]
    matches.sort(key=lambda item: float(item.get("x_factor") or 0), reverse=True)
    exemplars = matches[:5]
    return {
        "template_id": template_id,
        "examples": exemplars,
        "suggested_skeleton": [
            "hook: first 2–3 lines",
            "bridge: lived context",
            "meat: specific lesson",
            "mic drop: contrast",
            "optional CTA: real question",
        ],
        "warning": "Use this as structure, not copy. Credit distinctive visual concepts.",
    }


@mcp.tool()
def similar_images(query_text_or_path: str, threshold: float = 0.75) -> Dict[str, Any]:
    """Find nearest image-family matches for a local indexed image path.

    Text-to-image querying requires a Voyage key and is intentionally not done implicitly by the
    MCP server; supply a local image path after building the image index.
    """
    metadata = read_json(INTEL / "image-index.json", {})
    vector_path = INTEL / "image-vectors.npy"
    if not metadata.get("items") or not vector_path.exists():
        return {
            "matches": [],
            "status": "No image index. Run pipeline/embed.py images --allow-network first.",
        }
    requested = Path(query_text_or_path)
    target = (
        str(requested.relative_to(ROOT))
        if requested.is_absolute() and requested.is_relative_to(ROOT)
        else query_text_or_path
    )
    items = metadata["items"]
    index = next(
        (position for position, item in enumerate(items) if item.get("path") == target), None
    )
    if index is None:
        return {
            "matches": [],
            "status": (
                "Provide an indexed local image path; text queries are not implicit network calls."
            ),
        }
    vectors = np.load(vector_path)
    matches = []
    for position, item in enumerate(items):
        if position == index:
            continue
        similarity = cosine(vectors[index], vectors[position])
        if similarity >= threshold:
            matches.append({**item, "similarity": round(similarity, 4)})
    matches.sort(key=lambda item: item["similarity"], reverse=True)
    return {"matches": matches, "status": "ok"}


@mcp.tool()
def author_baseline(handle: str) -> Dict[str, Any]:
    """Show the latest computed baseline and post sample for one creator."""
    matches = [
        post
        for post in load_all_posts()
        if str(post.get("author_handle") or "").lower() == handle.lower()
    ]
    matches.sort(key=lambda item: str(item.get("posted_at") or ""), reverse=True)
    baselines = [
        post.get("author_baseline")
        for post in matches
        if isinstance(post.get("author_baseline"), (int, float))
    ]
    return {
        "handle": handle,
        "post_count": len(matches),
        "latest_baseline": baselines[0] if baselines else None,
        "posts": matches[:10],
    }


@mcp.tool()
def my_performance(window: int = 30) -> List[Dict[str, Any]]:
    """Return your own posts (flagged `is_mine`) for human performance review."""
    return my_posts(load_all_posts(), window=max(1, min(window, 100)))


@mcp.tool()
def log_story(text: str, pillars: List[str], metrics: Optional[List[str]] = None) -> Dict[str, Any]:
    """Create a story-bank intake file; supplied metrics remain unverified until evidence exists."""
    title = next(
        (line.strip("# ") for line in text.splitlines() if line.strip()), "Untitled story"
    )[:100]
    identifier = f"{slugify(title)}-{content_hash(text)[:6]}"
    destination = private_stories_dir() / f"{identifier}.md"
    if destination.exists():
        return {"status": "exists", "path": str(destination.relative_to(ROOT))}
    metric_lines = metrics or []
    frontmatter = [
        "---",
        f"id: {identifier}",
        f"title: {json.dumps(title)}",
        "date: unknown",
        f"pillars: [{', '.join(pillars)}]",
        "stage: unknown",
        'role_context: ""',
        "metrics:",
    ]
    for metric in metric_lines:
        frontmatter.extend(
            [f"  - claim: {json.dumps(metric)}", '    proof: ""', "    verified: false"]
        )
    if not metric_lines:
        frontmatter.append('  - claim: ""')
        frontmatter.append('    proof: ""')
        frontmatter.append("    verified: false")
    frontmatter.extend(
        [
            'tension: ""',
            'turn: ""',
            'result: ""',
            'lesson: ""',
            "emotions: []",
            "used_in: []",
            "---",
            "",
            "# What happened",
            "",
            text.strip(),
            "",
            "## Verification needed",
            "",
            "- Add evidence to each metric and then update `private/identity/truth-table.md`.",
            "",
        ]
    )
    destination.write_text("\n".join(frontmatter), encoding="utf-8")
    build_index()
    return {
        "status": "created",
        "path": str(destination.relative_to(ROOT)),
        "warning": "Metrics were recorded as unverified.",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
