"""Write a compact report for normalized posts explicitly marked `is_mine: true`."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from .common import ROOT, load_all_posts
except ImportError:  # pragma: no cover - direct script execution
    from common import ROOT, load_all_posts


def my_posts(posts: List[Dict[str, Any]], window: int | None = None) -> List[Dict[str, Any]]:
    """Return explicitly flagged self posts; this never guesses the owner's handle."""

    mine = [post for post in posts if post.get("is_mine")]
    mine.sort(key=lambda post: str(post.get("posted_at") or ""), reverse=True)
    return mine[:window] if window is not None else mine


def report(posts: List[Dict[str, Any]]) -> str:
    mine = my_posts(posts)
    lines = [
        "# My post performance",
        "",
        "Engagement is public engagement, not impressions.",
        "",
        "| Date | Hook | Engagement | X-factor | URL |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for post in mine:
        hook = str(post.get("hook") or "").replace("\n", " ").replace("|", "\\|")[:90]
        xfactor = (
            f"{post['x_factor']:.2f}" if isinstance(post.get("x_factor"), (int, float)) else "—"
        )
        cells = [
            str(post.get("posted_at") or "—")[:10],
            hook,
            str(post.get("engagement", 0)),
            xfactor,
            str(post.get("url") or "—"),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    destination = ROOT / "ops" / "metrics" / "my-performance.md"
    destination.write_text(report(load_all_posts()), encoding="utf-8")
    print(destination.relative_to(ROOT))
