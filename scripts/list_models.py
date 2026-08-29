"""List model IDs your configured endpoint actually serves. Never guess a model name.

    uv run python scripts/list_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import config  # noqa: E402  (must follow the sys.path insert above)


def main() -> None:
    base = (config.LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    key = config.llm_api_key()
    if not key:
        raise SystemExit(
            f"No API key found. Set {config.LLM_API_KEY_ENV} in .env "
            "(and LLM_BASE_URL if you are not using OpenAI)."
        )
    try:
        response = requests.get(
            f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise SystemExit(f"{base}/models -> {exc.response.status_code}: {exc.response.text[:300]}")
    except requests.RequestException as exc:
        raise SystemExit(f"Could not reach {base}: {type(exc).__name__}: {exc}")

    ids = sorted(str(item.get("id")) for item in response.json().get("data", []))
    print(f"{len(ids)} models at {base}\n")
    for model_id in ids:
        print(" ", model_id)


if __name__ == "__main__":
    main()
