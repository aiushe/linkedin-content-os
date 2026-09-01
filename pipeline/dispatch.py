"""Human-gated LinkedIn post dispatch via Apify.

Every send requires both --confirm and --allow-network. The li_at session cookie is read from
the environment at runtime and never written to logs, actor input files, or disk.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests

try:
    from .common import ROOT, read_json, split_frontmatter, utc_now, write_json
except ImportError:  # pragma: no cover - direct script execution
    from common import ROOT, read_json, split_frontmatter, utc_now, write_json

QUEUE_DIR = ROOT / "drafts" / "queue"
APPROVED_DIR = ROOT / "drafts" / "approved"
PUBLISHED_DIR = ROOT / "drafts" / "published"
DISPATCH_LOG = ROOT / "ops" / "dispatch-log.json"

DEFAULT_DAILY_LIMIT = 3


def _daily_limit() -> int:
    raw = os.getenv("DISPATCH_DAILY_LIMIT", "")
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_DAILY_LIMIT


def _dispatches_today(log: List[Dict[str, Any]]) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for entry in log if str(entry.get("date", "")).startswith(today))


def list_drafts() -> List[Dict[str, Any]]:
    """Return a summary of every draft in the queue and approved directories."""
    drafts: List[Dict[str, Any]] = []
    for directory in (QUEUE_DIR, APPROVED_DIR):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name.startswith("_") or path.name == ".gitkeep":
                continue
            text = path.read_text(encoding="utf-8")
            meta, _ = split_frontmatter(text)
            drafts.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "title": meta.get("title", path.stem),
                    "status": meta.get("status", "unknown"),
                    "type": meta.get("type", ""),
                    "claims_verdict": meta.get("claims_verdict", ""),
                    "voice_check": meta.get("voice_check", ""),
                    "confidential_terms_check": meta.get("confidential_terms_check", ""),
                    "created_at": meta.get("created_at", ""),
                }
            )
    return drafts


def preview(draft_path: Path) -> Dict[str, Any]:
    """Parse a queue draft and return its text, hooks, and observation summary."""
    text = draft_path.read_text(encoding="utf-8")
    meta, body = split_frontmatter(text)

    hooks: List[str] = []
    in_hooks = False
    body_lines: List[str] = []
    for line in body.splitlines():
        if line.strip().lower().startswith("## hook variant"):
            in_hooks = True
            continue
        if in_hooks and line.strip().startswith("## "):
            in_hooks = False
        if in_hooks and line.strip():
            hooks.append(line.strip().lstrip("0123456789. "))
        elif not in_hooks:
            body_lines.append(line)

    draft_text = "\n".join(body_lines).strip()
    # Strip the title heading that mirrors frontmatter
    lines = draft_text.splitlines()
    if lines and lines[0].startswith("# "):
        draft_text = "\n".join(lines[1:]).strip()

    return {
        "path": str(draft_path.relative_to(ROOT)),
        "title": meta.get("title", draft_path.stem),
        "type": meta.get("type", ""),
        "draft_text": draft_text,
        "hooks": hooks,
        "claims_verdict": meta.get("claims_verdict", ""),
        "voice_check": meta.get("voice_check", ""),
        "confidential_terms_check": meta.get("confidential_terms_check", ""),
        "unresolved_claim_spans": meta.get("unresolved_claim_spans", []),
        "created_at": meta.get("created_at", ""),
    }


def _post_via_apify(draft_text: str, actor_id: str, token: str, cookie: str) -> Dict[str, Any]:
    """Call the Apify posting actor. Token goes in header, never query params."""
    path_id = actor_id.replace("/", "~")
    endpoint = f"https://api.apify.com/v2/acts/{path_id}/run-sync-get-dataset-items"
    payload = {
        "cookie_li_at": cookie,
        "post_text": draft_text,
        "media_urls": [],
    }
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def send(draft_path: Path) -> Dict[str, Any]:
    """Dispatch a draft to LinkedIn and move it to published."""
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        return {"error": "Set APIFY_API_TOKEN in .env."}
    cookie = os.getenv("LINKEDIN_LI_AT_COOKIE")
    if not cookie:
        return {"error": "Set LINKEDIN_LI_AT_COOKIE in .env."}
    actor_id = os.getenv("APIFY_POST_ACTOR_ID", "curious_coder/linkedin-auto-poster")

    log = read_json(DISPATCH_LOG, [])
    if not isinstance(log, list):
        log = []
    limit = _daily_limit()
    if _dispatches_today(log) >= limit:
        return {"error": f"Daily dispatch limit reached ({limit}). Try again tomorrow."}

    info = preview(draft_path)
    draft_text = info["draft_text"]
    if not draft_text.strip():
        return {"error": "Draft body is empty."}

    _post_via_apify(draft_text, actor_id, token, cookie)

    now = utc_now()
    log_entry = {
        "date": now,
        "draft": info["path"],
        "title": info["title"],
        "type": info["type"],
        "actor_id": actor_id,
        "claims_verdict": info["claims_verdict"],
        "voice_check": info["voice_check"],
    }
    log.append(log_entry)
    write_json(DISPATCH_LOG, log)

    # Move draft to published with dispatch metadata
    text = draft_path.read_text(encoding="utf-8")
    text = text.replace("status: review", "status: published", 1)
    insertion = f"dispatched_at: {now}\n"
    text = text.replace("---\n\n", f"{insertion}---\n\n", 1)
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    destination = PUBLISHED_DIR / draft_path.name
    destination.write_text(text, encoding="utf-8")
    draft_path.unlink()

    return {
        "published": str(destination.relative_to(ROOT)),
        "dispatched_at": now,
        "actor_id": actor_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action")

    sub.add_parser("list", help="Show drafts ready for dispatch")

    preview_cmd = sub.add_parser("preview", help="Preview a draft before dispatch")
    preview_cmd.add_argument("--draft", required=True, type=Path)

    send_cmd = sub.add_parser("send", help="Dispatch a draft to LinkedIn")
    send_cmd.add_argument("--draft", required=True, type=Path)
    send_cmd.add_argument("--confirm", action="store_true")
    send_cmd.add_argument("--allow-network", action="store_true")

    args = parser.parse_args()

    if args.action == "list":
        drafts = list_drafts()
        if not drafts:
            print("No drafts in queue.")
            return
        for draft in drafts:
            flags = []
            if draft["claims_verdict"] and draft["claims_verdict"] != "pass":
                flags.append(f"claims:{draft['claims_verdict']}")
            if draft["voice_check"] and draft["voice_check"] != "pass":
                flags.append(f"voice:{draft['voice_check']}")
            if draft["confidential_terms_check"] and draft["confidential_terms_check"] != "pass":
                flags.append(f"confidential:{draft['confidential_terms_check']}")
            flag_str = f"  [{', '.join(flags)}]" if flags else ""
            print(f"  {draft['path']}  {draft['title']}{flag_str}")

    elif args.action == "preview":
        draft_path = ROOT / args.draft if not args.draft.is_absolute() else args.draft
        info = preview(draft_path)
        print(f"Title: {info['title']}")
        print(f"Type: {info['type']}")
        print(f"Claims: {info['claims_verdict']}  Voice: {info['voice_check']}  "
              f"Confidential: {info['confidential_terms_check']}")
        if info["unresolved_claim_spans"]:
            spans = info["unresolved_claim_spans"]
            if isinstance(spans, list):
                print(f"Unresolved claims: {', '.join(str(s) for s in spans)}")
        print(f"\n--- Draft ---\n{info['draft_text']}\n")
        if info["hooks"]:
            print("--- Hook variants ---")
            for i, hook in enumerate(info["hooks"], 1):
                print(f"  {i}. {hook}")

    elif args.action == "send":
        if not args.confirm:
            parser.error("Refusing to dispatch. Review the draft, then re-run with --confirm.")
        if not args.allow_network:
            parser.error("Refusing network access. Re-run with --allow-network.")
        draft_path = ROOT / args.draft if not args.draft.is_absolute() else args.draft
        if not draft_path.exists():
            parser.error(f"Draft not found: {draft_path}")
        result = send(draft_path)
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"Dispatched. Published to: {result['published']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
