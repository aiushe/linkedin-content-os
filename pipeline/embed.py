"""Create small on-disk Voyage embedding indexes with content-hash reuse.

The script never runs remotely unless invoked with `--allow-network` and a `VOYAGE_API_KEY`.
It uses the REST API directly, keeping the project dependency-light.
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import requests

try:
    from .common import INTEL, ROOT, content_hash, load_all_posts, load_stories, write_json
except ImportError:  # pragma: no cover - direct script execution
    from common import INTEL, ROOT, content_hash, load_all_posts, load_stories, write_json


TEXT_ENDPOINT = "https://api.voyageai.com/v1/embeddings"
MULTIMODAL_ENDPOINT = "https://api.voyageai.com/v1/multimodalembeddings"


def voyage_text(inputs: List[str], api_key: str, model: str) -> List[List[float]]:
    response = requests.post(
        TEXT_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"input": inputs, "model": model, "input_type": "document"},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    return [
        item["embedding"] for item in sorted(payload["data"], key=lambda item: item.get("index", 0))
    ]


def voyage_multimodal(inputs: List[Dict[str, Any]], api_key: str, model: str) -> List[List[float]]:
    response = requests.post(
        MULTIMODAL_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"inputs": inputs, "model": model, "input_type": "document"},
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    return [
        item["embedding"] for item in sorted(payload["data"], key=lambda item: item.get("index", 0))
    ]


def text_items(kind: str) -> List[Dict[str, Any]]:
    if kind == "stories":
        return [
            {
                "id": str(story.get("id")),
                "path": story.get("path"),
                "text": "\n".join(
                    str(story.get(key) or "")
                    for key in ("title", "tension", "turn", "result", "lesson")
                ),
            }
            for story in load_stories()
        ]
    return [
        {"id": str(post.get("id")), "path": post.get("url"), "text": str(post.get("text") or "")}
        for post in load_all_posts()
        if post.get("text")
    ]


def local_image_input(path: Path, caption: str = "") -> Dict[str, Any]:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "content": [
            {"type": "text", "text": caption or path.stem},
            {"type": "image_base64", "image_base64": f"data:{mime_type};base64,{encoded}"},
        ]
    }


def save_index(
    items: List[Dict[str, Any]], vectors: List[List[float]], prefix: str, model: str
) -> None:
    vector_path = INTEL / f"{prefix}-vectors.npy"
    metadata_path = INTEL / f"{prefix}-index.json"
    np.save(vector_path, np.asarray(vectors, dtype=np.float32))
    write_json(metadata_path, {"model": model, "items": items})


def embed_text(kind: str, api_key: str, model: str) -> int:
    items = text_items(kind)
    unique = [item for item in items if item["text"].strip()]
    vectors: List[List[float]] = []
    for start in range(0, len(unique), 128):
        batch = unique[start : start + 128]
        vectors.extend(voyage_text([item["text"] for item in batch], api_key, model))
    for item in unique:
        item["content_hash"] = content_hash(item["text"])
        item.pop("text", None)
    save_index(unique, vectors, "story" if kind == "stories" else "market", model)
    return len(unique)


def embed_images(api_key: str, model: str) -> int:
    items = []
    inputs = []
    for post in load_all_posts():
        image_path = post.get("image_path")
        path = ROOT / image_path if image_path else None
        if not path or not path.exists() or not path.is_file():
            continue
        items.append(
            {
                "id": post.get("id"),
                "path": image_path,
                "content_hash": content_hash(path.read_bytes().hex()),
            }
        )
        inputs.append(local_image_input(path, str(post.get("hook") or "")))
    vectors: List[List[float]] = []
    for start in range(0, len(inputs), 64):
        vectors.extend(voyage_multimodal(inputs[start : start + 64], api_key, model))
    save_index(items, vectors, "image", model)
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("stories", "market", "images"))
    parser.add_argument("--text-model", default="voyage-3")
    parser.add_argument("--multimodal-model", default="voyage-multimodal-3")
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args()
    if not args.allow_network:
        parser.error("Embedding has a usage cost. Re-run with --allow-network after review.")
    api_key = os.getenv("VOYAGE_API_KEY")
    if not api_key:
        parser.error("Set VOYAGE_API_KEY in .env/environment.")
    count = (
        embed_images(api_key, args.multimodal_model)
        if args.kind == "images"
        else embed_text(args.kind, api_key, args.text_model)
    )
    print(f"embedded {count} {args.kind}")


if __name__ == "__main__":
    main()
