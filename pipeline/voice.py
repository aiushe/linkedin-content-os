"""Compute a lightweight voice fingerprint and score drafts against it."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from .common import CORPUS, PRIVATE, ensure_private_identity_file, identity_file, write_json
except ImportError:  # pragma: no cover - direct script execution
    from common import CORPUS, PRIVATE, ensure_private_identity_file, identity_file, write_json


WORD_RE = re.compile(r"\b[\w']+\b")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}")
HEDGE_WORDS = {"maybe", "perhaps", "probably", "usually", "generally", "somewhat", "quite"}


def sample_paths() -> List[Path]:
    private_base = PRIVATE / "identity" / "voice" / "samples"
    base = private_base if private_base.exists() else CORPUS / "identity" / "voice" / "samples"
    return [
        path
        for path in sorted(base.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    ]


def words(text: str) -> List[str]:
    return WORD_RE.findall(text.lower())


def sentences(text: str) -> List[str]:
    return [piece.strip() for piece in SENTENCE_RE.split(text.strip()) if len(words(piece)) >= 2]


def mean_or_zero(items: Iterable[float]) -> float:
    values = list(items)
    return round(statistics.mean(values), 3) if values else 0.0


def pstdev_or_zero(items: Iterable[float]) -> float:
    values = list(items)
    return round(statistics.pstdev(values), 3) if len(values) > 1 else 0.0


def feature_set(text: str) -> Dict[str, Any]:
    tokens = words(text)
    sentence_lengths = [len(words(sentence)) for sentence in sentences(text)]
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text.strip()) if item.strip()]
    paragraph_lengths = [len(words(item)) for item in paragraphs]
    token_count = len(tokens) or 1
    first_words = " ".join(tokens[:18])
    first_nonempty = next((line.strip() for line in text.splitlines() if line.strip()), "")
    opening = (
        "question"
        if first_nonempty.endswith("?")
        else "number"
        if re.match(r"^[\d$%]", first_nonempty)
        else "scene_or_claim"
    )
    return {
        "word_count": len(tokens),
        "paragraph_count": len(paragraphs),
        "sentence_length_median": round(statistics.median(sentence_lengths), 3)
        if sentence_lengths
        else 0.0,
        "sentence_length_stdev": pstdev_or_zero(sentence_lengths),
        "paragraph_length_mean": mean_or_zero(paragraph_lengths),
        "paragraph_length_stdev": pstdev_or_zero(paragraph_lengths),
        "contraction_rate": round(
            len(re.findall(r"\b\w+(?:n't|'re|'ve|'ll|'d|'m)\b", text.lower())) / token_count, 4
        ),
        "first_person_rate": round(
            sum(token in {"i", "me", "my", "mine", "we", "our", "us"} for token in tokens)
            / token_count,
            4,
        ),
        "hedge_rate": round(sum(token in HEDGE_WORDS for token in tokens) / token_count, 4),
        "em_dash_rate": round(text.count("—") / token_count, 4),
        "semicolon_rate": round(text.count(";") / token_count, 4),
        "colon_rate": round(text.count(":") / token_count, 4),
        "parenthetical_rate": round(len(re.findall(r"\([^)]{1,120}\)", text)) / token_count, 4),
        "type_token_ratio": round(len(set(tokens)) / token_count, 4),
        "mean_word_length": round(mean_or_zero([len(token) for token in tokens]), 3),
        "list_line_rate": round(
            sum(line.lstrip().startswith(("- ", "* ", "• ")) for line in text.splitlines())
            / max(len(text.splitlines()), 1),
            4,
        ),
        "opening_move": opening,
        "opening_preview": first_words,
    }


def aggregate(samples: List[str]) -> Dict[str, Any]:
    features = [feature_set(sample) for sample in samples if words(sample)]
    if not features:
        return {"sample_count": 0, "word_count": 0, "features": {}}
    numeric_keys = [
        key
        for key, value in features[0].items()
        if isinstance(value, (int, float)) and key != "word_count"
    ]
    profile = {}
    for key in numeric_keys:
        values = [float(item[key]) for item in features]
        profile[key] = {"mean": mean_or_zero(values), "stdev": pstdev_or_zero(values)}
    opening_counts: Dict[str, int] = {}
    for item in features:
        opening = str(item["opening_move"])
        opening_counts[opening] = opening_counts.get(opening, 0) + 1
    return {
        "sample_count": len(features),
        "word_count": sum(int(item["word_count"]) for item in features),
        "features": profile,
        "opening_moves": opening_counts,
    }


def replace_fingerprint(profile: Dict[str, Any]) -> None:
    path = ensure_private_identity_file("voice.md")
    text = path.read_text(encoding="utf-8")
    block = "```json\n" + json.dumps(profile, indent=2) + "\n```"
    updated, count = re.subn(r"```json\n.*?\n```", block, text, count=1, flags=re.DOTALL)
    if not count:
        raise ValueError("voice.md must contain a JSON fingerprint code block")
    path.write_text(updated, encoding="utf-8")


def load_fingerprint() -> Dict[str, Any]:
    text = identity_file("voice.md").read_text(encoding="utf-8")
    match = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    return json.loads(match.group(1)) if match else {}


def banned_tells() -> List[str]:
    text = identity_file("voice.md").read_text(encoding="utf-8")
    section = re.search(r"## Starting banned tells\n(.*?)(?:\n## |\Z)", text, re.DOTALL)
    if not section:
        return []
    return [line[2:].strip("` ") for line in section.group(1).splitlines() if line.startswith("- ")]


def score_text(text: str, profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    profile = profile or load_fingerprint()
    current = feature_set(text)
    baseline = profile.get("features", {})
    flags = []
    for key, expected in baseline.items():
        if key not in current or not isinstance(expected, dict):
            continue
        mean, stdev = expected.get("mean", 0), expected.get("stdev", 0)
        if stdev and abs(float(current[key]) - float(mean)) > (1.5 * float(stdev)):
            flags.append(
                {
                    "feature": key,
                    "actual": current[key],
                    "expected_mean": mean,
                    "expected_stdev": stdev,
                }
            )
    lower = text.lower()
    tells = [tell for tell in banned_tells() if tell.lower() in lower]
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_line.endswith("?") and "rhetorical-question openers" not in tells:
        tells.append("rhetorical-question opener")
    return {
        "features": current,
        "flags": flags,
        "banned_tells": tells,
        "passes_deterministic_gate": not flags and not tells,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("fingerprint", help="Build the profile from corpus voice samples")
    score = subparsers.add_parser("score", help="Score one draft against the stored profile")
    score.add_argument("draft", type=Path)
    score.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "fingerprint":
        profile = aggregate([path.read_text(encoding="utf-8") for path in sample_paths()])
        replace_fingerprint(profile)
        print(json.dumps(profile, indent=2))
        return
    result = score_text(args.draft.read_text(encoding="utf-8"))
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
