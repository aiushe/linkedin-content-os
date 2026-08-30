"""Normalize a scraper actor's raw payload into stable local post records."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

try:  # Supports both `python pipeline/normalize.py` and `import pipeline.normalize`.
    from .common import (
        INTEL,
        canonical_post,
        extract_raw_records,
        read_json,
        slugify,
        utc_now,
        write_json,
    )
except ImportError:  # pragma: no cover - direct script execution
    from common import (
        INTEL,
        canonical_post,
        extract_raw_records,
        read_json,
        slugify,
        utc_now,
        write_json,
    )


def normalize_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    actor: Optional[str] = None,
    my_handle: Optional[str] = None,
) -> Path:
    payload = read_json(input_path)
    if payload is None:
        raise FileNotFoundError(input_path)
    scraped_at = utc_now()
    posts = [canonical_post(record, scraped_at) for record in extract_raw_records(payload)]
    if my_handle:
        selected_handle = my_handle.strip().lower()
        for post in posts:
            post["is_mine"] = str(post.get("author_handle") or "").lower() == selected_handle
    name = actor or input_path.stem
    destination = output_path or INTEL / "posts" / f"{scraped_at[:10]}-{slugify(name)}.json"
    write_json(destination, posts)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Raw JSON saved by an actor")
    parser.add_argument("--output", type=Path, help="Normalized post JSON destination")
    parser.add_argument("--actor", help="Actor/creator label used in the default filename")
    parser.add_argument(
        "--my-handle",
        help="Explicit public handle to flag as your own posts; never inferred from a pull.",
    )
    args = parser.parse_args()
    print(normalize_file(args.input, args.output, args.actor, args.my_handle))


if __name__ == "__main__":
    main()
