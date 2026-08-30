"""Discover reusable text templates and image families from local embedding indexes."""

from __future__ import annotations

import argparse
import statistics
from collections import Counter
from typing import Any, Iterable, List

import numpy as np

try:
    from .common import INTEL, iter_post_files, read_json, write_json
    from .voice import feature_set
except ImportError:  # pragma: no cover - direct script execution
    from common import INTEL, iter_post_files, read_json, write_json
    from voice import feature_set


STRUCTURAL_NUMERIC_FEATURES = (
    "paragraph_count",
    "sentence_length_median",
    "sentence_length_stdev",
    "list_line_rate",
    "contraction_rate",
)
DEFAULT_STRUCTURAL_DISTANCE = 0.9


def normalized(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def greedy_clusters(vectors: np.ndarray, threshold: float) -> List[int]:
    if not len(vectors):
        return []
    vectors = normalized(vectors)
    representatives: List[np.ndarray] = []
    labels: List[int] = []
    for vector in vectors:
        if not representatives:
            representatives.append(vector)
            labels.append(1)
            continue
        similarities = [float(np.dot(vector, representative)) for representative in representatives]
        index, similarity = max(enumerate(similarities), key=lambda item: item[1])
        if similarity >= threshold:
            labels.append(index + 1)
            centroid = np.vstack([representatives[index], vector]).mean(axis=0)
            representatives[index] = centroid / (np.linalg.norm(centroid) or 1)
        else:
            representatives.append(vector)
            labels.append(len(representatives))
    return labels


def _standardised_rows(rows: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    """Convert measured shape features to comparable z scores, without embeddings."""

    scales: dict[str, tuple[float, float]] = {}
    for key in STRUCTURAL_NUMERIC_FEATURES:
        values = [float(row[key]) for row in rows]
        mean = statistics.mean(values) if values else 0.0
        stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
        scales[key] = (mean, stdev or 1.0)
    return [
        {
            **{
                key: (float(row[key]) - scales[key][0]) / scales[key][1]
                for key in STRUCTURAL_NUMERIC_FEATURES
            },
            "opening_move": str(row["opening_move"]),
            "paragraph_band": _paragraph_band(int(row["paragraph_count"])),
        }
        for row in rows
    ]


def _paragraph_band(count: int) -> str:
    """Use durable writing-shape bands rather than treating one and many paragraphs alike."""

    if count <= 1:
        return "one"
    if count <= 3:
        return "two_to_three"
    if count <= 6:
        return "four_to_six"
    if count <= 10:
        return "seven_to_ten"
    return "eleven_plus"


def _structural_distance(left: dict[str, float | str], right: dict[str, float | str]) -> float:
    """Average shape difference in standard deviations; opening moves must agree."""

    if (
        left["opening_move"] != right["opening_move"]
        or left["paragraph_band"] != right["paragraph_band"]
    ):
        return float("inf")
    return statistics.mean(
        abs(float(left[key]) - float(right[key])) for key in STRUCTURAL_NUMERIC_FEATURES
    )


def structural_clusters(
    texts: Iterable[str], distance: float = DEFAULT_STRUCTURAL_DISTANCE
) -> List[int]:
    """Cluster post shapes from local stylometric features, not topical embeddings.

    A cluster requires an identical opening move and paragraph-count band. Every
    member must also remain within ``distance`` average standard deviations for
    sentence rhythm, list-line rate, and contraction rate. The fixed default is
    a documented shape definition, not a corpus-fitted threshold.
    """

    rows = [feature_set(text) for text in texts]
    standardised = _standardised_rows(rows)
    members: list[list[dict[str, float | str]]] = []
    labels: list[int] = []
    for row in standardised:
        eligible = [
            (
                index,
                max(_structural_distance(row, existing) for existing in cluster_members),
            )
            for index, cluster_members in enumerate(members)
        ]
        index, nearest = (
            min(eligible, key=lambda item: item[1]) if eligible else (0, float("inf"))
        )
        if nearest <= distance:
            labels.append(index + 1)
            members[index].append(row)
        else:
            members.append([row])
            labels.append(len(members))
    return labels


def cluster_size_distribution(labels: Iterable[int | None]) -> dict[int, int]:
    """Return ``{cluster_size: number_of_clusters}`` for review-friendly reporting."""

    counts = Counter(label for label in labels if isinstance(label, int))
    return dict(sorted(Counter(counts.values()).items()))


def _all_post_records() -> list[tuple[Any, list[dict[str, Any]], dict[str, Any]]]:
    records: list[tuple[Any, list[dict[str, Any]], dict[str, Any]]] = []
    for path in iter_post_files():
        payload = read_json(path, [])
        if not isinstance(payload, list):
            continue
        records.extend((path, payload, post) for post in payload if isinstance(post, dict))
    return records


def annotate_posts(prefix: str, field: str, threshold: float) -> int:
    metadata = read_json(INTEL / f"{prefix}-index.json", {})
    vectors_path = INTEL / f"{prefix}-vectors.npy"
    if not vectors_path.exists() or not metadata.get("items"):
        raise FileNotFoundError(f"Missing {prefix} embedding index; run pipeline/embed.py first.")
    items = metadata["items"]
    labels = greedy_clusters(np.load(vectors_path), threshold)
    assignments = {str(item.get("id")): label for item, label in zip(items, labels)}
    updated = 0
    for path in iter_post_files():
        payload = read_json(path, [])
        if not isinstance(payload, list):
            continue
        for post in payload:
            if str(post.get("id")) in assignments:
                post[field] = assignments[str(post["id"])]
                updated += 1
        write_json(path, payload)
    return updated


def annotate_structural_posts(distance: float = DEFAULT_STRUCTURAL_DISTANCE) -> int:
    """Assign text-template IDs from post structure only; no index is required."""

    records = _all_post_records()
    labels = structural_clusters([str(post.get("text") or "") for _, _, post in records], distance)
    by_path: dict[Any, list[dict[str, Any]]] = {}
    for (path, payload, post), label in zip(records, labels):
        post["template_id"] = label
        by_path[path] = payload
    for path, payload in by_path.items():
        write_json(path, payload)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("text", "images"))
    parser.add_argument(
        "--method",
        choices=("structural", "semantic"),
        default="structural",
        help="Text defaults to local structural shapes; semantic embeddings remain opt-in.",
    )
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--distance", type=float, default=DEFAULT_STRUCTURAL_DISTANCE)
    args = parser.parse_args()
    before = cluster_size_distribution(
        [post.get("template_id") for _, _, post in _all_post_records()]
    )
    if args.kind == "text" and args.method == "structural":
        updated = annotate_structural_posts(args.distance)
        after = cluster_size_distribution(
            [post.get("template_id") for _, _, post in _all_post_records()]
        )
        print(f"before structural clustering: {before or 'no template IDs'}")
        print(f"after structural clustering: {after or 'no template IDs'}")
        print(f"annotated {updated} posts")
        return
    prefix, field, default = (
        ("market", "template_id", 0.84)
        if args.kind == "text"
        else ("image", "image_family_id", 0.80)
    )
    print(f"semantic clustering (before): {before or 'no template IDs'}")
    print(f"annotated {annotate_posts(prefix, field, args.threshold or default)} posts")


if __name__ == "__main__":
    main()
