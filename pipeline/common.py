"""Shared filesystem, markdown, and post-record helpers.

The project intentionally stores its small datasets in inspectable files. These helpers keep
those reads and writes predictable without introducing a database or a YAML dependency.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]

try:  # Every pipeline CLI imports this module, so .env reaches all of them from one place.
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass
CORPUS = ROOT / "corpus"
INTEL = ROOT / "intel"
PRIVATE = ROOT / "private"


def identity_file(name: str) -> Path:
    """Return a local personal identity file when present, otherwise its tracked template."""
    private_path = PRIVATE / "identity" / name
    return private_path if private_path.exists() else CORPUS / "identity" / name


def ensure_private_identity_file(name: str) -> Path:
    """Create a local copy of an identity template before writing user-specific data."""
    destination = PRIVATE / "identity" / name
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    template = CORPUS / "identity" / name
    if template.exists():
        destination.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        destination.touch()
    return destination


def private_stories_dir() -> Path:
    """Return the ignored story-bank directory, creating it only when a story is written."""
    destination = PRIVATE / "stories"
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def slugify(value: str, fallback: str = "unknown") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        # Apify actors sometimes return a Unix timestamp in seconds or milliseconds.
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def iso_datetime(value: Any) -> Optional[str]:
    parsed = parse_datetime(value)
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z") if parsed else None


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def first_present(record: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def first_lines(text: str, count: int = 3) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n") if line.strip()]
    return "\n".join(lines[:count])


def extract_raw_records(payload: Any) -> List[Dict[str, Any]]:
    """Unwrap the common list/data/items response shapes used by scraper actors."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "data", "posts", "results"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return [payload]


def numeric(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.lower().replace(",", "").strip()
        multiplier = 1
        if cleaned.endswith("k"):
            multiplier, cleaned = 1000, cleaned[:-1]
        elif cleaned.endswith("m"):
            multiplier, cleaned = 1_000_000, cleaned[:-1]
        try:
            return int(float(cleaned) * multiplier)
        except ValueError:
            pass
    return 0


def profile_handle_from_url(value: Any) -> str:
    """Extract a LinkedIn profile or company handle from a collection target URL."""

    parsed = urlparse(str(value or ""))
    parts = [unquote(part).strip() for part in parsed.path.split("/") if part.strip()]
    for index, part in enumerate(parts[:-1]):
        if part.lower() in {"in", "company"}:
            return parts[index + 1]
    return ""


def source_profile_handle(raw: Dict[str, Any]) -> str:
    """Return the watchlist profile whose feed supplied a record, when the actor provides it."""

    query = raw.get("query")
    query_target = (
        first_present(query, "targetUrl", "profileUrl", "url", default="")
        if isinstance(query, dict)
        else ""
    )
    reposted_by = raw.get("repostedBy") or {}
    if not isinstance(reposted_by, dict):
        reposted_by = {}
    return str(
        profile_handle_from_url(query_target)
        or first_present(reposted_by, "publicIdentifier", "handle", "username", "slug", default="")
    )


def canonical_post(raw: Dict[str, Any], scraped_at: str | None = None) -> Dict[str, Any]:
    """Map a permissive actor response into the repository's stable post contract."""
    author = raw.get("author") or raw.get("authorProfile") or raw.get("profile") or {}
    if not isinstance(author, dict):
        author = {}
    engagement = raw.get("engagement") or raw.get("engagementStats") or {}
    if not isinstance(engagement, dict):
        engagement = {}
    text = str(first_present(raw, "text", "postText", "content", "description", default=""))
    original_author_handle = str(
        first_present(author, "publicIdentifier", "handle", "username", "slug", default="")
        or first_present(raw, "author_handle", "authorHandle", "authorPublicIdentifier", default="")
    )
    original_author_name = str(
        first_present(author, "name", "fullName", default="")
        or first_present(raw, "author_name", "authorName", default="")
    )
    source_handle = source_profile_handle(raw)
    author_handle = source_handle or original_author_handle
    reposted_by = raw.get("repostedBy") or {}
    if not isinstance(reposted_by, dict):
        reposted_by = {}
    author_name = str(
        first_present(reposted_by, "name", "fullName", default="")
        if source_handle
        else original_author_name
    ) or original_author_name
    media = raw.get("media") or raw.get("images") or raw.get("image") or []
    media_type = str(first_present(raw, "media_type", "mediaType", "type", default="none")).lower()
    if media_type not in {"image", "carousel", "video", "document", "none"}:
        media_type = "image" if media else "none"
    likes = numeric(
        first_present(engagement, "likes", "likeCount", default=None)
        or first_present(raw, "likes", "likeCount")
    )
    comments = numeric(
        first_present(engagement, "comments", "commentCount", default=None)
        or first_present(raw, "comments", "commentCount")
    )
    shares = numeric(
        first_present(engagement, "shares", "reposts", "shareCount", "repostCount", default=None)
        or first_present(raw, "shares", "reposts", "shareCount", "repostCount")
    )
    url = str(first_present(raw, "url", "postUrl", "linkedinUrl", default=""))
    raw_id = first_present(raw, "id", "urn", "postId", "activityUrn", default=None)
    identifier = str(raw_id or url or content_hash(f"{author_handle}|{text}"))
    posted_value = first_present(raw, "posted_at", "postedAt", "createdAt", "date", "timestamp")
    if isinstance(posted_value, dict):
        posted_value = first_present(posted_value, "timestamp", "date")
    return {
        "id": identifier if identifier.startswith("linkedin:") else f"linkedin:{identifier}",
        "platform": "linkedin",
        "author_handle": author_handle,
        "author_name": author_name,
        "source_profile_handle": source_handle or None,
        "original_author_handle": original_author_handle or None,
        "original_author_name": original_author_name or None,
        "author_info": str(first_present(author, "headline", "description", default="")),
        "url": url,
        "posted_at": iso_datetime(posted_value),
        "scraped_at": scraped_at or utc_now(),
        "text": text,
        "hook": first_lines(text),
        "char_count": len(text),
        "media_type": media_type,
        "image_path": None,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "engagement": likes + (3 * comments) + (5 * shares),
        "author_baseline": None,
        "x_factor": None,
        "funnel": None,
        "structure": {},
        "template_id": None,
        "image_family_id": None,
        "is_mine": bool(raw.get("is_mine", False)),
    }


def iter_post_files() -> Iterable[Path]:
    yield from sorted((INTEL / "posts").glob("*.json"))


def load_all_posts() -> List[Dict[str, Any]]:
    posts: List[Dict[str, Any]] = []
    for path in iter_post_files():
        payload = read_json(path, [])
        if isinstance(payload, list):
            posts.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            candidate = payload.get("posts", [payload])
            posts.extend(item for item in candidate if isinstance(item, dict))
    return posts


def split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Parse the small YAML subset used by story frontmatter without extra dependencies."""
    if not text.startswith("---\n"):
        return {}, text
    closing = text.find("\n---", 4)
    if closing < 0:
        return {}, text
    header = text[4:closing].strip().splitlines()
    body = text[closing + 4 :].lstrip("\n")
    data: Dict[str, Any] = {}
    active_list: str | None = None
    active_mapping: Dict[str, Any] | None = None
    for raw_line in header:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        line = raw_line.rstrip()
        if line.startswith("  - ") and active_list:
            value = line[4:].strip()
            if ":" in value:
                key, item_value = value.split(":", 1)
                active_mapping = {key.strip(): parse_scalar(item_value.strip())}
                data[active_list].append(active_mapping)
            else:
                data[active_list].append(parse_scalar(value))
            continue
        if line.startswith("    ") and active_mapping and ":" in line:
            key, item_value = line.strip().split(":", 1)
            active_mapping[key.strip()] = parse_scalar(item_value.strip())
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if not value:
            data[key] = []
            active_list = key
            active_mapping = None
        else:
            data[key] = parse_scalar(value)
            active_list = None
            active_mapping = None
    return data, body


def parse_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        return [
            item.strip().strip('"').strip("'") for item in value[1:-1].split(",") if item.strip()
        ]
    return value


def load_stories() -> List[Dict[str, Any]]:
    stories: List[Dict[str, Any]] = []
    story_dirs = (PRIVATE / "stories", CORPUS / "stories")
    for story_dir in story_dirs:
        for path in sorted(story_dir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
            if not metadata:
                continue
            metadata["path"] = str(path.relative_to(ROOT))
            metadata["body"] = body.strip()
            stories.append(metadata)
    return stories
