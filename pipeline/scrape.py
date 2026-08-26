"""Explicit, opt-in Apify actor wrapper for a known public-post scraper.

Use Apify MCP for exploratory pulls first. This wrapper exists only after you have selected an
actor, understood its input schema and price, and deliberately choose to repeat that pull.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

import requests

try:
    from .common import INTEL, slugify, utc_now, write_json
except ImportError:  # pragma: no cover - direct script execution
    from common import INTEL, slugify, utc_now, write_json


def run_actor(actor_id: str, actor_input: Dict[str, Any], token: str) -> Any:
    endpoint = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    response = requests.post(endpoint, params={"token": token}, json=actor_input, timeout=300)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, type=Path, help="Actor input JSON reviewed by you"
    )
    parser.add_argument("--actor-id", default=os.getenv("APIFY_ACTOR_ID"))
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required acknowledgement before a paid network call",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.allow_network:
        parser.error("Refusing network access. Review the actor, then re-run with --allow-network.")
    if not args.actor_id:
        parser.error("Provide --actor-id or APIFY_ACTOR_ID.")
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        parser.error("Set APIFY_API_TOKEN in .env/environment; never put it in actor input JSON.")
    actor_input = json.loads(args.input.read_text(encoding="utf-8"))
    serialized = json.dumps(actor_input).lower()
    if any(key in serialized for key in ("cookie", "li_at", "session")):
        parser.error(
            "Actor input appears to contain a session/cookie field. "
            "This wrapper refuses personal-session scraping."
        )
    result = run_actor(args.actor_id, actor_input, token)
    destination = args.output or INTEL / "raw" / f"{utc_now()[:10]}-{slugify(args.actor_id)}.json"
    write_json(destination, result)
    print(destination)


if __name__ == "__main__":
    main()
