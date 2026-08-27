"""The sole write node, reachable only after a human approval interrupt."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from agent.state import DraftState
from pipeline import common


def _title(value: str) -> str:
    first_line = next(
        (line.strip("# ").strip() for line in value.splitlines() if line.strip()), "Draft"
    )
    return first_line[:100]


def _update_story_used_in(story: dict, draft_id: str) -> None:
    """Record episodic use only in a private story file, never a tracked template."""

    raw_path = story.get("path")
    if not raw_path:
        return
    path = common.ROOT / str(raw_path)
    private_stories = common.PRIVATE / "stories"
    if not path.exists() or not path.is_relative_to(private_stories):
        return
    metadata, _ = common.split_frontmatter(path.read_text(encoding="utf-8"))
    used_in = metadata.get("used_in") if isinstance(metadata.get("used_in"), list) else []
    if draft_id in used_in:
        return
    used_in.append(draft_id)
    text = path.read_text(encoding="utf-8")
    replacement = "used_in: " + json.dumps(used_in)
    updated, count = re.subn(r"(?m)^used_in:\s*.*$", replacement, text, count=1)
    if count:
        path.write_text(updated, encoding="utf-8")


def commit(state: DraftState) -> dict:
    """Write a review artifact only after a passing gate and explicit approval."""

    if state.get("decision") != "approve":
        return {"terminal_reason": "Commit blocked: approval was not received."}
    if state.get("gate_verdict") != "pass":
        return {"terminal_reason": "Commit blocked: draft does not have a passing gate report."}
    now = datetime.now(timezone.utc)
    title = _title(state.get("draft", ""))
    date = now.date().isoformat()
    stem = f"{date}-{common.slugify(title)[:60]}"
    destination = common.ROOT / "drafts" / "queue" / f"{stem}.md"
    suffix = 2
    while destination.exists():
        destination = common.ROOT / "drafts" / "queue" / f"{stem}-{suffix}.md"
        suffix += 1
    draft_id = destination.stem
    stories = state.get("stories", [])
    story_ids = [str(story["id"]) for story in stories if story.get("id")]
    first_story = next(iter(stories), {})
    pillars = first_story.get("pillars") if isinstance(first_story.get("pillars"), list) else []
    template = state.get("template") or {}
    template_id = template.get("template_id") if isinstance(template, dict) else None
    review_notes = [
        "- Truth-table/stories checked: deterministic claims gate passed.",
        "- Voice-check flags resolved: deterministic voice gate passed.",
        "- Image brief / attribution: human review required.",
    ]
    review_notes += [
        f"- Degraded grounding: {reason}" for reason in state.get("degradation_reasons", [])
    ]
    review_notes += [
        f"- Reviewer annotation: {note}"
        for note in state.get("critique", {}).get("annotations", [])
    ]
    frontmatter = [
        "---",
        f"title: {json.dumps(title)}",
        "status: review",
        f"type: {state.get('intent', 'authority')}",
        f"pillar: {json.dumps(pillars[0] if pillars else '')}",
        f"story_ids: {json.dumps(story_ids)}",
        f"template_id: {json.dumps(template_id)}",
        "claims_checked: true",
        "voice_check: pass",
        f"created_at: {now.isoformat()}",
        "---",
        "",
        f"# {title}",
        "",
        state.get("draft", "").strip(),
        "",
        "## Hook variants",
        "",
    ]
    frontmatter += [
        f"{index}. {hook}" for index, hook in enumerate(state.get("hooks", []), start=1)
    ]
    frontmatter += ["", "## Review notes", "", *review_notes, ""]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(frontmatter), encoding="utf-8")
    for story in stories:
        _update_story_used_in(story, draft_id)
    return {
        "queue_path": str(destination.relative_to(common.ROOT)),
        "terminal_reason": "Queued for review.",
    }
