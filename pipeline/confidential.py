"""Advisory detection of human-maintained confidential terms.

The local term list is intentionally private and optional. Matches are reported to
the human reviewer, but confidentiality findings never determine whether a draft
can be approved. The Git boundary, not this advisory check, keeps local drafts out
of the public repository.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from . import common

ConfidentialVerdict = Literal["pass", "warn"]


@dataclass
class ConfidentialTermsReport:
    verdict: ConfidentialVerdict
    matched_terms: list[str]
    matched_lines: dict[str, list[int]]
    term_count: int
    reason: str


def terms_path() -> Path:
    """Return the ignored term-list path without creating it."""

    return common.PRIVATE / "confidential-terms.md"


def load_terms(path: Path | None = None) -> set[str] | None:
    """Read one Markdown-list term per line, ignoring comments and placeholders."""

    source = path or terms_path()
    if not source.is_file():
        return None
    terms: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        value = re.sub(r"^\s*[-*+]\s+", "", line).strip().strip("`")
        if not value or value.startswith("#") or (value.startswith("[") and value.endswith("]")):
            continue
        terms.add(value)
    return terms


def check(draft: str, terms: set[str] | None = None) -> ConfidentialTermsReport:
    """Warn on configured literal matches without blocking a human decision."""

    configured = load_terms() if terms is None else terms
    if not configured:
        return ConfidentialTermsReport(
            verdict="pass",
            matched_terms=[],
            matched_lines={},
            term_count=0,
            reason="Confidential-term list is not configured; advisory check was skipped.",
        )
    matched_lines: dict[str, list[int]] = {}
    for term in sorted(configured, key=str.lower):
        matches = list(re.finditer(rf"(?<!\w){re.escape(term)}(?!\w)", draft, re.IGNORECASE))
        if matches:
            matched_lines[term] = [draft.count("\n", 0, match.start()) + 1 for match in matches]
    matched = list(matched_lines)
    return ConfidentialTermsReport(
        verdict="warn" if matched else "pass",
        matched_terms=matched,
        matched_lines=matched_lines,
        term_count=len(configured),
        reason=(
            "Matched confidential term(s); human review is required before approval."
            if matched
            else "No configured confidential terms found."
        ),
    )
