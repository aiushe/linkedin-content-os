"""Central configuration for the agent harness.

Keep data-dependent thresholds here so corpus seeding changes configuration rather
than graph logic.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # Load .env so a key in the project file reaches os.environ.
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass

ROUTER_CONFIDENCE_FLOOR = float(os.getenv("ROUTER_CONFIDENCE_FLOOR", "0.70"))
VOICE_Z_THRESHOLD = float(os.getenv("VOICE_Z_THRESHOLD", "1.5"))
VOICE_MIN_SAMPLES = int(os.getenv("VOICE_MIN_SAMPLES", "3"))
VOICE_MIN_WORDS = int(os.getenv("VOICE_MIN_WORDS", "1500"))
MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "3"))
CLAIM_REQUIRE_EXACT = True

MODEL_ROUTER = os.getenv("MODEL_ROUTER", "gpt-4o-mini")
MODEL_WRITER = os.getenv("MODEL_WRITER", "gpt-4.1")
MODEL_CRITIC = os.getenv("MODEL_CRITIC", "gpt-4o-mini")

# --- Live market intel cost controls -------------------------------------
# Timeliness can help both reach posts and story-grounded authority posts choose a
# differentiated shape. It never contributes facts; comments stay excluded.
INTEL_ENABLED_INTENTS = frozenset(
    filter(None, os.getenv("INTEL_ENABLED_INTENTS", "authority,reach").split(","))
)
INTEL_MAX_POSTS = int(os.getenv("INTEL_MAX_POSTS", "25"))  # actor spend cap per call
INTEL_TOP_K = int(os.getenv("INTEL_TOP_K", "5"))  # how many reach an LLM context
INTEL_HOOK_CHARS = int(os.getenv("INTEL_HOOK_CHARS", "200"))  # per-post context budget
INTEL_CACHE_TTL_HOURS = float(os.getenv("INTEL_CACHE_TTL_HOURS", "12"))
INTEL_USD_PER_POST = float(os.getenv("INTEL_USD_PER_POST", "0.0015"))  # $1.50 / 1k posts
INTEL_MIN_ALIVE = int(os.getenv("INTEL_MIN_ALIVE", "8"))
INTEL_POSTED_LIMIT = os.getenv("INTEL_POSTED_LIMIT", "week")
MODEL_INTEL = os.getenv("MODEL_INTEL", "gpt-4o-mini")
# Conservative estimate for one bounded 400-token-in / 80-token-out mini call.
INTEL_SATURATION_ESTIMATED_USD = float(os.getenv("INTEL_SATURATION_ESTIMATED_USD", "0.00011"))

RETRY_MAX = int(os.getenv("RETRY_MAX", "2"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.5"))


def live_models_enabled() -> bool:
    """Return whether model calls are explicitly available for this process.

    Tests and first-run local installs work offline. Production uses live models as
    soon as an OpenAI key is present, unless the user explicitly sets AGENT_OFFLINE.
    """

    return bool(os.getenv("OPENAI_API_KEY")) and os.getenv("AGENT_OFFLINE", "").lower() not in {
        "1",
        "true",
        "yes",
    }
