#!/usr/bin/env python3
"""Build inspectable market reports from local normalized post records only."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import common, voice  # noqa: E402

REPORTS = common.INTEL / "reports"


def _escape(value: object) -> str:
    return str(value or "—").replace("\n", " ").replace("|", "\\|").strip()


def _ranked_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (post for post in posts if isinstance(post.get("x_factor"), (int, float))),
        key=lambda post: (float(post["x_factor"]), int(post.get("engagement") or 0)),
        reverse=True,
    )


def top_posts_report(posts: list[dict[str, Any]], limit: int = 25) -> str:
    """Render the plan's morning-read report without generating editorial content."""

    lines = [
        "# Top market posts",
        "",
        "Ranked from local normalized data by x-factor. Hooks and links are source records, "
        "not claims.",
        "",
        "| X-factor | Hook | Link | Image path |",
        "| ---: | --- | --- | --- |",
    ]
    for post in _ranked_posts(posts)[:limit]:
        lines.append(
            "| "
            + " | ".join(
                (
                    f"{float(post['x_factor']):.2f}",
                    _escape(post.get("hook")),
                    _escape(post.get("url")),
                    _escape(post.get("image_path")),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def template_library_report(posts: list[dict[str, Any]]) -> str:
    """Describe reusable structural clusters while omitting singleton non-templates."""

    by_template: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        if isinstance(post.get("template_id"), int):
            by_template[int(post["template_id"])].append(post)
    lines = [
        "# Structural template library",
        "",
        "Clusters are based on local post shape, not semantic topic. Singleton clusters are "
        "not templates.",
    ]
    for template_id, members in sorted(by_template.items()):
        if len(members) < 2:
            continue
        exemplar = _ranked_posts(members)[0] if _ranked_posts(members) else members[0]
        features = voice.feature_set(str(exemplar.get("text") or ""))
        lines.extend(
            [
                "",
                f"## Template {template_id} · {len(members)} posts",
                "",
                "- Shape: "
                f"{features['paragraph_count']} paragraphs; "
                f"median sentence length {features['sentence_length_median']}; "
                f"opening {features['opening_move']}; "
                f"list-line rate {features['list_line_rate']}; "
                f"contraction rate {features['contraction_rate']}.",
                f"- Exemplar hook: {_escape(exemplar.get('hook'))}",
                f"- Exemplar link: {_escape(exemplar.get('url'))}",
                f"- Exemplar image path: {_escape(exemplar.get('image_path'))}",
            ]
        )
    return "\n".join(lines) + "\n"


def build(destination: Path = REPORTS) -> tuple[Path, Path]:
    """Write both plan-declared reports from current local intel."""

    destination.mkdir(parents=True, exist_ok=True)
    posts = common.load_all_posts()
    top_posts = destination / "top-posts.md"
    templates = destination / "template-library.md"
    top_posts.write_text(top_posts_report(posts), encoding="utf-8")
    templates.write_text(template_library_report(posts), encoding="utf-8")
    return top_posts, templates


if __name__ == "__main__":
    for path in build():
        print(path.relative_to(common.ROOT))
