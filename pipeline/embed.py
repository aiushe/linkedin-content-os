"""Create small on-disk embedding indexes with content-hash reuse.

Text embeddings default to OpenAI (`text-embedding-3-small`), reusing the OPENAI_API_KEY
this project already needs. Voyage remains selectable with `--provider voyage`.

Image embeddings are Voyage-only: OpenAI publishes no multimodal embedding endpoint. That
path is preserved rather than removed, and fails with a clear message if no Voyage key exists.

Never runs remotely without `--allow-network`. Uses REST directly to stay dependency-light.
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


# Any OpenAI-compatible endpoint. EMBED_BASE_URL falls back to LLM_BASE_URL so a single
# provider switch covers chat and embeddings together.
_BASE = (os.getenv("EMBED_BASE_URL") or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
OPENAI_TEXT_ENDPOINT = f"{_BASE}/embeddings"
VOYAGE_TEXT_ENDPOINT = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MULTIMODAL_ENDPOINT = "https://api.voyageai.com/v1/multimodalembeddings"

# voyage-3 / voyage-multimodal-3 are deprecated and excluded from Voyage's free tier.
DEFAULT_TEXT_MODEL = {"openai": "text-embedding-3-small", "voyage": "voyage-3.5"}
DEFAULT_MULTIMODAL_MODEL = "voyage-multimodal-3.5"
KEY_ENV = {
    "openai": os.getenv("EMBED_API_KEY_ENV") or os.getenv("LLM_API_KEY_ENV", "OPENAI_API_KEY"),
    "voyage": "VOYAGE_API_KEY",
}


def resolve_text_model(provider: str, text_model: str | None = None) -> str:
    """Prefer an explicit CLI model, then the configured provider-specific override."""

    return text_model or os.getenv("EMBED_MODEL_OVERRIDE") or DEFAULT_TEXT_MODEL[provider]


def embed_text_batch(
    inputs: List[str], api_key: str, model: str, provider: str = "openai"
) -> List[List[float]]:
    """Both providers accept {input, model} and return data[].embedding with an index."""

    payload: Dict[str, Any] = {"input": inputs, "model": model}
    if provider == "voyage":
        payload["input_type"] = "document"
    response = requests.post(
        VOYAGE_TEXT_ENDPOINT if provider == "voyage" else OPENAI_TEXT_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    return [
        item["embedding"] for item in sorted(payload["data"], key=lambda item: item.get("index", 0))
    ]


def voyage_multimodal(inputs: List[Dict[str, Any]], api_key: str, model: str) -> List[List[float]]:
    response = requests.post(
        VOYAGE_MULTIMODAL_ENDPOINT,
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


def embed_text(kind: str, api_key: str, model: str, provider: str = "openai") -> int:
    items = text_items(kind)
    unique = [item for item in items if item["text"].strip()]
    vectors: List[List[float]] = []
    for start in range(0, len(unique), 128):
        batch = unique[start : start + 128]
        vectors.extend(
            embed_text_batch([item["text"] for item in batch], api_key, model, provider)
        )
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
    parser.add_argument(
        "--provider",
        choices=("openai", "voyage"),
        default=os.getenv("EMBED_PROVIDER", "openai"),
        help="Text embedding provider. Images are always Voyage.",
    )
    parser.add_argument("--text-model", default=None)
    parser.add_argument("--multimodal-model", default=DEFAULT_MULTIMODAL_MODEL)
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args()
    if not args.allow_network:
        parser.error("Embedding has a usage cost. Re-run with --allow-network after review.")

    provider = "voyage" if args.kind == "images" else args.provider
    env_name = KEY_ENV[provider]
    api_key = os.getenv(env_name)
    if not api_key:
        hint = (
            " Image embeddings are Voyage-only; OpenAI has no multimodal embedding endpoint."
            if args.kind == "images"
            else ""
        )
        parser.error(f"Set {env_name} in .env/environment.{hint}")

    count = (
        embed_images(api_key, args.multimodal_model)
        if args.kind == "images"
        else embed_text(
            args.kind, api_key, resolve_text_model(provider, args.text_model), provider
        )
    )
    print(f"embedded {count} {args.kind}")


if __name__ == "__main__":
    main()
