"""Build a transparent metadata index over the story bank.

Metadata filtering is intentionally the default retrieval layer. Vector embeddings can be added
later, but are not required for a small story bank.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .common import INTEL, content_hash, load_stories, write_json
except ImportError:  # pragma: no cover - direct script execution
    from common import INTEL, content_hash, load_stories, write_json


def safe_story(story: Dict[str, Any]) -> Dict[str, Any]:
    metrics = story.get("metrics") if isinstance(story.get("metrics"), list) else []
    return {
        "id": story.get("id"),
        "title": story.get("title"),
        "date": story.get("date"),
        "pillars": story.get("pillars", []),
        "stage": story.get("stage"),
        "role_context": story.get("role_context", ""),
        "tension": story.get("tension", ""),
        "turn": story.get("turn", ""),
        "result": story.get("result", ""),
        "lesson": story.get("lesson", ""),
        "emotions": story.get("emotions", []),
        "metrics": metrics,
        "has_verified_metric": any(
            isinstance(metric, dict) and metric.get("verified") is True for metric in metrics
        ),
        "path": story.get("path"),
        "content_hash": content_hash(json.dumps(story, sort_keys=True, default=str)),
    }


def build_index(destination: Optional[Path] = None) -> Path:
    target = destination or INTEL / "story-index.json"
    stories = [safe_story(story) for story in load_stories()]
    write_json(target, {"version": 1, "stories": stories})
    return target


if __name__ == "__main__":
    print(build_index())
