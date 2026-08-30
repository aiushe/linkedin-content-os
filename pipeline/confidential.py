"""Fail-closed detection of human-maintained confidential terms.

The local term list is intentionally private and optional to create.  An absent or
empty list is an indeterminate result, never a pass, so a draft cannot enter the
queue until its owner has explicitly configured this safeguard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from . import common

ConfidentialVerdict = Literal["pass", "block", "indeterminate"]


@dataclass
class ConfidentialTermsReport:
    verdict: ConfidentialVerdict
    matched_terms: list[str]
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
    """Block configured literal matches; fail closed if the list is not ready."""

    configured = load_terms() if terms is None else terms
    if not configured:
        return ConfidentialTermsReport(
            verdict="indeterminate",
            matched_terms=[],
            term_count=0,
            reason="Confidential-term gate is not configured; add private/confidential-terms.md.",
        )
    matched = [
        term
        for term in sorted(configured, key=str.lower)
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", draft, re.IGNORECASE)
    ]
    return ConfidentialTermsReport(
        verdict="block" if matched else "pass",
        matched_terms=matched,
        term_count=len(configured),
        reason=(
            "Matched confidential term(s)."
            if matched
            else "No configured confidential terms found."
        ),
    )
