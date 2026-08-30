from __future__ import annotations

from pipeline import cluster


def test_structural_clustering_groups_similar_shapes_without_embeddings():
    texts = [
        "What changed?\n\nI wrote a short lesson.\n\n- One point\n- Two points",
        "Why now?\n\nI wrote another lesson.\n\n- One point\n- Two points",
        "42 lessons from a launch. This is a long single-paragraph reflection without list lines.",
    ]

    labels = cluster.structural_clusters(texts)

    assert labels[0] == labels[1]
    assert labels[2] != labels[0]
    assert cluster.cluster_size_distribution(labels) == {1: 1, 2: 1}


def test_structural_clustering_accepts_empty_input():
    assert cluster.structural_clusters([]) == []
