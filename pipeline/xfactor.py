"""Compute per-author, self-excluded 30-day engagement x-factors for normalized posts."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, Iterable, List

try:
    from .common import iter_post_files, parse_datetime, read_json, write_json
except ImportError:  # pragma: no cover - direct script execution
    from common import iter_post_files, parse_datetime, read_json, write_json


def engagement(post: Dict[str, Any], mode: str = "weighted") -> int:
    if mode == "likes":
        return int(post.get("likes") or 0)
    return (
        int(post.get("likes") or 0)
        + (3 * int(post.get("comments") or 0))
        + (5 * int(post.get("shares") or 0))
    )


def score_posts(
    posts: Iterable[Dict[str, Any]], mode: str = "weighted", minimum_sample: int = 10
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for post in posts:
        handle = str(post.get("author_handle") or post.get("author_name") or "unknown").lower()
        post["engagement"] = engagement(post, mode)
        grouped[handle].append(post)
    for author_posts in grouped.values():
        for post in author_posts:
            current = parse_datetime(post.get("posted_at"))
            if not current:
                post["author_baseline"] = None
                post["x_factor"] = None
                continue
            start = current - timedelta(days=30)
            baseline_posts = [
                item
                for item in author_posts
                if item is not post
                and (posted := parse_datetime(item.get("posted_at"))) is not None
                and start <= posted < current
            ]
            if len(baseline_posts) < minimum_sample:
                post["author_baseline"] = None
                post["x_factor"] = None
                continue
            baseline = sum(int(item["engagement"]) for item in baseline_posts) / len(baseline_posts)
            post["author_baseline"] = round(baseline, 2)
            post["x_factor"] = round(post["engagement"] / baseline, 3) if baseline else None
    return list(posts)


def score_repo(mode: str, minimum_sample: int) -> int:
    all_posts: List[Dict[str, Any]] = []
    sources = []
    for path in iter_post_files():
        payload = read_json(path, [])
        records = payload if isinstance(payload, list) else payload.get("posts", [])
        if isinstance(records, list):
            all_posts.extend(record for record in records if isinstance(record, dict))
            sources.append((path, records))
    score_posts(all_posts, mode=mode, minimum_sample=minimum_sample)
    for path, records in sources:
        write_json(path, records)
    return len(all_posts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("weighted", "likes"), default="weighted")
    parser.add_argument("--minimum-sample", type=int, default=10)
    args = parser.parse_args()
    print(f"scored {score_repo(args.mode, args.minimum_sample)} posts")


if __name__ == "__main__":
    main()
