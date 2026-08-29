"""Pull one public LinkedIn profile via the Apify actor and save it for review.

Writes the raw actor payload to private/profile/raw-<date>.json and a readable
private/profile/current.md. Never overwrites an existing current.md without --force.

Usage:
    uv run python pipeline/pull_profile.py https://www.linkedin.com/in/<handle>/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT / "private" / "profile"
ACTOR = "harvestapi~linkedin-profile-scraper"
MODE = "Profile details no email ($4 per 1k)"


def token() -> str:
    value = os.environ.get("APIFY_API_TOKEN")
    if value:
        return value
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("APIFY_API_TOKEN=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip("\"'")
    sys.exit("APIFY_API_TOKEN not found in the environment or .env")


def run(url: str) -> list:
    payload = json.dumps({"urls": [url], "profileScraperMode": MODE}).encode()
    endpoint = (
        f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={token()}"
    )
    request = urllib.request.Request(
        endpoint, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read())


def render(item: dict) -> str:
    def text(value) -> str:
        """Locations and dates arrive as nested dicts; flatten to a display string."""
        if isinstance(value, dict):
            for key in ("text", "linkedinText", "name", "title"):
                if value.get(key):
                    return str(value[key])
            return ""
        return str(value or "")

    name = " ".join(x for x in [item.get("firstName"), item.get("lastName")] if x)
    location = text(item.get("location"))
    if isinstance(item.get("location"), dict):
        parsed = item["location"].get("parsed") or {}
        location = parsed.get("text") or location

    lines = [
        "# Current LinkedIn profile",
        "",
        f"- Pulled: {date.today().isoformat()} via Apify {ACTOR}",
        f"- Profile: {item.get('linkedinUrl') or ''}",
        f"- Public identifier: {item.get('publicIdentifier') or ''}",
        f"- Followers: {item.get('followerCount')} | Connections: {item.get('connectionsCount')}"
        f" | Open to work: {item.get('openToWork')}",
        "- Snapshot of the LIVE profile. Do not edit by hand; re-pull instead.",
        "",
        f"## Name\n\n{name}",
        f"\n## Headline\n\n{item.get('headline') or ''}",
        f"\n## Location\n\n{location}",
        f"\n## About\n\n{item.get('about') or ''}",
        "\n## Experience\n",
    ]
    for role in item.get("experience") or []:
        start = text(role.get("startDate"))
        end = text(role.get("endDate"))
        span = " - ".join(x for x in [start, end] if x)
        meta = " | ".join(
            x for x in [span, role.get("duration"), role.get("employmentType")] if x
        )
        lines.append(f"### {role.get('position') or ''} - {role.get('companyName') or ''}")
        lines.append(f"*{meta}*\n")
        if role.get("description"):
            lines.append(f"{role['description']}\n")

    lines.append("\n## Education\n")
    for edu in item.get("education") or []:
        parts = [
            edu.get("schoolName") or edu.get("title") or "",
            edu.get("degree") or edu.get("subtitle") or "",
            text(edu.get("startDate")),
            text(edu.get("endDate")),
        ]
        lines.append("- " + " | ".join(x for x in parts if x))

    lines.append("\n## Top skills (pinned on profile)\n")
    for skill in item.get("topSkills") or []:
        lines.append(f"- {text(skill) if not isinstance(skill, str) else skill}")

    lines.append("\n## All skills listed\n")
    for skill in item.get("skills") or []:
        lines.append(f"- {skill.get('name') if isinstance(skill, dict) else skill}")

    lines.append("\n## Certifications\n")
    for cert in item.get("certifications") or []:
        lines.append(f"- {cert.get('title') if isinstance(cert, dict) else cert}")

    featured = item.get("featured")
    lines.append(f"\n## Featured\n\n{'(empty)' if not featured else featured}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--force", action="store_true", help="overwrite an existing current.md")
    args = parser.parse_args()

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    items = run(args.url)
    if not items:
        sys.exit("Actor returned no items. Check the URL is a public profile.")

    raw = PROFILE_DIR / f"raw-{date.today().isoformat()}.json"
    raw.write_text(json.dumps(items, indent=2))

    current = PROFILE_DIR / "current.md"
    if current.exists() and not args.force:
        alt = PROFILE_DIR / f"pulled-{date.today().isoformat()}.md"
        alt.write_text(render(items[0]))
        print(f"current.md exists; wrote {alt} instead (use --force to replace)")
    else:
        current.write_text(render(items[0]))
        print(f"wrote {current}")
    print(f"raw payload: {raw}")


if __name__ == "__main__":
    main()
