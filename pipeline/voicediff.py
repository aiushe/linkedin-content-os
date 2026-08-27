"""Mine generated-to-published edits into reviewable voice-rule candidates.

This tool suggests patterns; it never mutates `voice.md`. Promote only consistent patterns with
three or more observations.
"""

from __future__ import annotations

import argparse
import difflib
import re
from collections import Counter
from pathlib import Path
from typing import List

try:
    from .common import PRIVATE, ROOT
except ImportError:  # pragma: no cover - direct script execution
    from common import PRIVATE, ROOT


def normalized_lines(path: Path) -> List[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("---")
    ]


def compare(generated: Path, published: Path) -> str:
    diff = list(difflib.ndiff(normalized_lines(generated), normalized_lines(published)))
    removed = [line[2:] for line in diff if line.startswith("- ")]
    added = [line[2:] for line in diff if line.startswith("+ ")]
    removed_words = Counter(re.findall(r"\b[a-zA-Z']+\b", " ".join(removed).lower()))
    added_words = Counter(re.findall(r"\b[a-zA-Z']+\b", " ".join(added).lower()))
    lines = [
        f"# Edit analysis · {published.stem}",
        "",
        f"- Removed lines: {len(removed)}",
        f"- Added lines: {len(added)}",
        "",
        "## Candidate word substitutions",
    ]
    candidates = []
    for word, count in removed_words.most_common():
        if count >= 2 and added_words.get(word, 0) == 0 and len(word) > 3:
            candidates.append(
                f"- You removed `{word}` {count} times. "
                "Track across at least 3 drafts before banning it."
            )
    lines.extend(candidates[:10] or ["- No repeatable word pattern in this single pair yet."])
    lines.extend(
        [
            "",
            "## Diff",
            "```diff",
            *difflib.unified_diff(
                normalized_lines(generated),
                normalized_lines(published),
                fromfile=str(generated),
                tofile=str(published),
                lineterm="",
            ),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generated", type=Path)
    parser.add_argument("published", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or PRIVATE / "identity" / "voice" / "edits" / f"{args.published.stem}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(compare(args.generated, args.published), encoding="utf-8")
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
