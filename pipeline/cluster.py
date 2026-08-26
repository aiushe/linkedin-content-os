"""Discover reusable text templates and image families from local embedding indexes."""

from __future__ import annotations

import argparse
from typing import List

import numpy as np

try:
    from .common import INTEL, iter_post_files, read_json, write_json
except ImportError:  # pragma: no cover - direct script execution
    from common import INTEL, iter_post_files, read_json, write_json


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("text", "images"))
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()
    prefix, field, default = (
        ("market", "template_id", 0.84)
        if args.kind == "text"
        else ("image", "image_family_id", 0.80)
    )
    print(f"annotated {annotate_posts(prefix, field, args.threshold or default)} posts")


if __name__ == "__main__":
    main()
