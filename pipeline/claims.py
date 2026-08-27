"""Fail-closed claim extraction and grounding checks.

The module deliberately uses no model calls. It only permits numeric and
superlative assertions that occur exactly in the verified truth table or a
verified story metric.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from . import common

ClaimKind = Literal["numeric", "superlative", "attribution"]
ClaimVerdict = Literal["pass", "block", "indeterminate"]
FactSource = Literal["truth_table", "story_metric"]


@dataclass(frozen=True)
class Claim:
    sentence: str
    span: str
    kind: ClaimKind
    line_no: int


@dataclass(frozen=True)
class AllowedFact:
    claim: str
    proof: str
    period: str
    source: FactSource
    source_ref: str


@dataclass
class ClaimsReport:
    verdict: ClaimVerdict
    claims: list[Claim]
    matched: list[tuple[Claim, AllowedFact]]
    unmatched: list[Claim]
    narrative_only_hits: list[Claim]
    allowlist_size: int


TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
NUMERIC_RE = re.compile(
    r"(?<![\w#])\d[\d,]*(?:\.\d+)?(?:\s*(?:%|percent\b|x\b|k\b|m\b|"
    r"hours?\b|days?\b|weeks?\b|users?\b|customers?\b|tickets?\b|reps?\b))?",
    re.IGNORECASE,
)
SUPERLATIVE_RE = re.compile(
    r"\b(?:first|only|fastest|largest|best|number\s+one|industry-leading|best-in-class)\b|#1\b",
    re.IGNORECASE,
)
ATTRIBUTION_RE = re.compile(
    r"\b(?:according to|our data shows|we measured|studies show)\b", re.IGNORECASE
)
LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
WORD_RE = re.compile(r"[a-z0-9]+")


def _cells(line: str) -> list[str]:
    """Return Markdown-table cells without requiring a Markdown dependency."""

    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_verified(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "✓"}


def parse_truth_table(md: str) -> tuple[list[AllowedFact], set[str]]:
    """Parse only verified rows from a specifically identified Markdown table.

    A table becomes an allowlist only when its header includes ``Verified``. Other
    three-column tables are captured as narrative-only context and can never grant
    permission for a factual assertion.
    """

    allowed: list[AllowedFact] = []
    narrative_only: set[str] = set()
    lines = md.splitlines()
    index = 0
    while index < len(lines):
        header_line = lines[index]
        if (
            "|" not in header_line
            or index + 1 >= len(lines)
            or not TABLE_SEPARATOR_RE.match(lines[index + 1])
        ):
            index += 1
            continue
        header = _cells(header_line)
        header_lower = [cell.lower() for cell in header]
        rows: list[list[str]] = []
        cursor = index + 2
        while cursor < len(lines) and "|" in lines[cursor] and lines[cursor].strip():
            if not TABLE_SEPARATOR_RE.match(lines[cursor]):
                row = _cells(lines[cursor])
                if len(row) >= len(header):
                    rows.append(row)
            cursor += 1

        if "verified" in header_lower:
            verified_index = header_lower.index("verified")
            claim_index = next(
                (
                    position
                    for position, value in enumerate(header_lower)
                    if value in {"claim", "fact"}
                ),
                0,
            )
            proof_index = next(
                (position for position, value in enumerate(header_lower) if "proof" in value),
                None,
            )
            period_index = next(
                (
                    position
                    for position, value in enumerate(header_lower)
                    if "date" in value or "period" in value
                ),
                None,
            )
            for row in rows:
                claim = row[claim_index].strip()
                if (
                    not claim
                    or claim.startswith("[")
                    or verified_index >= len(row)
                    or not _is_verified(row[verified_index])
                ):
                    continue
                allowed.append(
                    AllowedFact(
                        claim=claim,
                        proof=row[proof_index].strip() if proof_index is not None else "",
                        period=row[period_index].strip() if period_index is not None else "",
                        source="truth_table",
                        source_ref="truth-table.md",
                    )
                )
        elif len(header) >= 3 and any(value in {"fact", "claim"} for value in header_lower):
            for row in rows:
                fact = row[0].strip()
                if fact and not fact.startswith("["):
                    narrative_only.add(fact)
        index = max(cursor, index + 1)
    return allowed, narrative_only


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(common.ROOT))
    except ValueError:
        return str(path)


def load_allowlist() -> list[AllowedFact]:
    """Load verified truth-table claims plus only verified story metrics."""

    truth_path = common.identity_file("truth-table.md")
    allowed, _ = parse_truth_table(truth_path.read_text(encoding="utf-8"))
    allowed = [
        AllowedFact(
            claim=fact.claim,
            proof=fact.proof,
            period=fact.period,
            source="truth_table",
            source_ref=_relative(truth_path),
        )
        for fact in allowed
    ]
    for story in common.load_stories():
        metrics = story.get("metrics") if isinstance(story.get("metrics"), list) else []
        for metric in metrics:
            if not isinstance(metric, dict) or metric.get("verified") is not True:
                continue
            claim = str(metric.get("claim") or "").strip()
            if not claim or claim.startswith("["):
                continue
            allowed.append(
                AllowedFact(
                    claim=claim,
                    proof=str(metric.get("proof") or ""),
                    period=str(story.get("date") or ""),
                    source="story_metric",
                    source_ref=str(story.get("path") or story.get("id") or "story"),
                )
            )
    return allowed


def _draft_lines(draft_body: str) -> list[tuple[int, str]]:
    """Remove frontmatter and review notes without altering source line numbers."""

    lines = draft_body.splitlines()
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                lines = ["" for _ in range(index + 1)] + lines[index + 1 :]
                break
    for index, line in enumerate(lines):
        if re.match(r"^\s*##\s+review notes\b", line, re.IGNORECASE):
            lines = lines[:index]
            break
    return [(number, LIST_MARKER_RE.sub("", line)) for number, line in enumerate(lines, start=1)]


def _is_year(span: str) -> bool:
    compact = span.replace(",", "").strip()
    return compact.isdigit() and len(compact) == 4 and 1990 <= int(compact) <= 2099


def extract_claims(draft_body: str) -> list[Claim]:
    """Extract auditable claim spans while excluding metadata and list markers."""

    claims: list[Claim] = []
    seen: set[tuple[int, int, str]] = set()
    for line_no, line in _draft_lines(draft_body):
        for sentence_match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", line):
            sentence = sentence_match.group(0).strip()
            if not sentence:
                continue
            for pattern, kind in (
                (NUMERIC_RE, "numeric"),
                (SUPERLATIVE_RE, "superlative"),
                (ATTRIBUTION_RE, "attribution"),
            ):
                for match in pattern.finditer(sentence):
                    span = match.group(0)
                    if kind == "numeric" and _is_year(span):
                        continue
                    key = (line_no, match.start(), kind)
                    if key not in seen:
                        claims.append(Claim(sentence, span, kind, line_no))
                        seen.add(key)
    return claims


def _normalise(value: str) -> str:
    value = value.lower().replace(",", "")
    value = re.sub(r"(\d)\s*(?:%|percent\b)", r"\1percent", value)
    value = re.sub(r"(\d)\s*x\b", r"\1x", value)
    return re.sub(r"\s+", " ", value).strip()


def _narrative_match(claim: Claim, narrative_only: set[str]) -> bool:
    sentence_words = set(WORD_RE.findall(_normalise(claim.sentence)))
    for fact in narrative_only:
        normalised_fact = _normalise(fact)
        if normalised_fact and (normalised_fact in _normalise(claim.sentence)):
            return True
        fact_words = {word for word in WORD_RE.findall(normalised_fact) if len(word) >= 4}
        if len(sentence_words & fact_words) >= 2:
            return True
    return False


def check(draft_body: str, allowlist: list[AllowedFact] | None = None) -> ClaimsReport:
    """Return a fail-closed factual-grounding report for a draft body."""

    if allowlist is None:
        allowlist = load_allowlist()
    truth_path = common.identity_file("truth-table.md")
    _, narrative_only = parse_truth_table(truth_path.read_text(encoding="utf-8"))
    claims = extract_claims(draft_body)
    matched: list[tuple[Claim, AllowedFact]] = []
    unmatched: list[Claim] = []
    narrative_hits: list[Claim] = []
    for claim in claims:
        fact = next(
            (
                candidate
                for candidate in allowlist
                if _normalise(claim.span) in _normalise(candidate.claim)
            ),
            None,
        )
        if fact is not None:
            matched.append((claim, fact))
        elif claim.kind in {"numeric", "superlative"}:
            unmatched.append(claim)
        if _narrative_match(claim, narrative_only):
            narrative_hits.append(claim)
    verdict: ClaimVerdict
    if not allowlist:
        verdict = "indeterminate"
    elif unmatched or narrative_hits:
        verdict = "block"
    else:
        verdict = "pass"
    return ClaimsReport(
        verdict=verdict,
        claims=claims,
        matched=matched,
        unmatched=unmatched,
        narrative_only_hits=narrative_hits,
        allowlist_size=len(allowlist),
    )
