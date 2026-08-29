"""Focused-role preflight for profile rewrites.

This node intentionally writes nowhere. A scattered target set must halt before profile copy is
generated, and a focused target set is returned as reviewable analysis rather than silently
rewriting a profile.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from agent.state import DraftState
from pipeline import common

MINIMUM_JDS = 5
COVERAGE_FLOOR = 0.75
GENERIC_TERMS = frozenset(
    {
        "about",
        "across",
        "ability",
        "and",
        "are",
        "building",
        "candidate",
        "company",
        "customers",
        "experience",
        "for",
        "from",
        "have",
        "help",
        "in",
        "including",
        "job",
        "looking",
        "our",
        "product",
        "role",
        "skills",
        "strong",
        "team",
        "teams",
        "the",
        "their",
        "this",
        "to",
        "with",
        "work",
        "working",
        "you",
        "your",
    }
)


def _significant_terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z][a-z0-9+-]{2,}", text.lower())
        if term not in GENERIC_TERMS
    }


def _role_cluster(text: str) -> str:
    """Return a role-family label without exposing an employer or target account name."""

    sample = text.lower()[:2_000]
    if "product operations" in sample or "product ops" in sample:
        return "product operations"
    if "technical program manager" in sample or "program management" in sample:
        return "technical program management"
    if "product manager" in sample or "product management" in sample:
        return "product management"
    return "other product role"


def analyze_jds(directory: Path) -> dict:
    """Compute document-frequency coverage and role clusters for a JD set."""

    paths = sorted(path for path in directory.glob("*.md") if path.is_file())
    documents = [path.read_text(encoding="utf-8") for path in paths]
    term_sets = [_significant_terms(document) for document in documents]
    frequencies: Counter[str] = Counter(term for terms in term_sets for term in terms)
    significant = set(frequencies)
    converged = {term for term, count in frequencies.items() if count >= 4}
    coverage = len(converged) / len(significant) if significant else 0.0
    clusters = sorted({_role_cluster(document) for document in documents})
    conflicting = sorted(
        (term for term, count in frequencies.items() if count < 4),
        key=lambda term: (frequencies[term], term),
    )[:20]
    return {
        "jd_count": len(documents),
        "coverage": round(coverage, 4),
        "coverage_floor": COVERAGE_FLOOR,
        "converged_term_count": len(converged),
        "significant_term_count": len(significant),
        "role_clusters": clusters,
        "conflicting_terms": conflicting,
        "focused": len(documents) >= MINIMUM_JDS and coverage >= COVERAGE_FLOOR,
    }


def profile_rewrite(_: DraftState) -> dict:
    """Halt unsafe profile rewrites before drafting any profile content."""

    analysis = analyze_jds(common.PRIVATE / "targets" / "jds")
    if analysis["jd_count"] < MINIMUM_JDS:
        return {
            "profile_analysis": analysis,
            "errors": [
                {
                    "node": "profile_rewrite",
                    "class": "input",
                    "message": (
                        "Profile rewrite halted: at least five job descriptions are required."
                    ),
                    "detail": f"found={analysis['jd_count']}",
                }
            ],
            "terminal_reason": (
                "Profile rewrite stopped: add at least five focused job descriptions."
            ),
        }
    if not analysis["focused"]:
        return {
            "profile_analysis": analysis,
            "errors": [
                {
                    "node": "profile_rewrite",
                    "class": "focus",
                    "message": "Profile rewrite halted: job-description coverage is below 0.75.",
                    "detail": (
                        f"coverage={analysis['coverage']}; "
                        f"clusters={', '.join(analysis['role_clusters'])}; "
                        f"conflicts={', '.join(analysis['conflicting_terms'])}"
                    ),
                }
            ],
            "terminal_reason": (
                "Profile rewrite stopped: the target roles are scattered. Choose one role cluster "
                f"before any profile is drafted: {', '.join(analysis['role_clusters'])}."
            ),
        }
    return {
        "profile_analysis": analysis,
        "terminal_reason": (
            "Profile rewrite preflight passed. Profile copy remains pending explicit human review."
        ),
    }
