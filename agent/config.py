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
VOICE_SHORT_POST_EXCLUDED_FEATURES = frozenset(
    feature.strip()
    for feature in os.getenv(
        "VOICE_SHORT_POST_EXCLUDED_FEATURES",
        "paragraph_length_mean,paragraph_length_stdev",
    ).split(",")
    if feature.strip()
)
MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "3"))
CLAIM_REQUIRE_EXACT = os.getenv("CLAIM_REQUIRE_EXACT", "true").lower() in {"1", "true", "yes"}

# Any OpenAI-compatible endpoint works here: OpenAI (default), Nebius Token Factory,
# Fireworks, or a local server. Only the base URL and key env var change.
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None
LLM_API_KEY_ENV = os.getenv("LLM_API_KEY_ENV", "OPENAI_API_KEY")


def llm_api_key() -> str | None:
    """Key for the configured endpoint.

    Only falls back to OPENAI_API_KEY when no distinct key env was configured. Sending an
    OpenAI key to a third-party base_url would fail confusingly rather than obviously.
    """

    key = os.getenv(LLM_API_KEY_ENV)
    if key:
        return key
    return os.getenv("OPENAI_API_KEY") if LLM_API_KEY_ENV == "OPENAI_API_KEY" else None


MODEL_ROUTER = os.getenv("MODEL_ROUTER", "gpt-4o-mini")
MODEL_WRITER = os.getenv("MODEL_WRITER", "gpt-4.1")
MODEL_CRITIC = os.getenv("MODEL_CRITIC", "gpt-4o-mini")
WRITER_TEMPERATURE = float(os.getenv("WRITER_TEMPERATURE", "0"))
_llm_seed = os.getenv("LLM_SEED", "").strip()
LLM_SEED = int(_llm_seed) if _llm_seed else None
# Bound each provider request. A timeout escalates the run; it must never leave a paid
# inference request waiting indefinitely.
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "180"))
LLM_HARD_TIMEOUT_SECONDS = float(os.getenv("LLM_HARD_TIMEOUT_SECONDS", "240"))

# --- Approved personal-memory boundary -----------------------------------
# Mem0 is optional convenience context. It can guide framing and preferences, but it is never
# factual evidence and must not make a claims gate pass. A static query avoids exporting the raw
# draft idea to a second provider on every run.
MEM0_API_KEY = os.getenv("MEM0_API_KEY") or None
MEM0_ENABLED = os.getenv("MEM0_ENABLED", "true").lower() in {"1", "true", "yes"}
MEM0_USER_ID = os.getenv("MEM0_USER_ID", "profile-memory")
MEM0_TIMEOUT_SECONDS = float(os.getenv("MEM0_TIMEOUT_SECONDS", "8"))
MEM0_TOP_K = int(os.getenv("MEM0_TOP_K", "6"))
MEM0_ALLOW_LANGSMITH_TRACING = os.getenv("MEM0_ALLOW_LANGSMITH_TRACING", "").lower() in {
    "1",
    "true",
    "yes",
}


def mem0_service_enabled() -> bool:
    """Return whether approved Mem0 operations may contact the managed service."""

    return bool(MEM0_API_KEY) and MEM0_ENABLED and os.getenv("AGENT_OFFLINE", "").lower() not in {
        "1",
        "true",
        "yes",
    }


def mem0_prompt_enabled() -> bool:
    """Keep personal-memory text out of LangSmith traces unless separately approved."""

    tracing = os.getenv("LANGSMITH_TRACING", "").lower() in {"1", "true", "yes"}
    return mem0_service_enabled() and (not tracing or MEM0_ALLOW_LANGSMITH_TRACING)

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

# Hard bounds on the two calls that can block forever. An unbounded network wait does
# not raise, so `except Exception` never fires and the graph hangs instead of degrading.
INTEL_TIMEOUT_SECONDS = float(os.getenv("INTEL_TIMEOUT_SECONDS", "25"))
GROUND_RECURSION_LIMIT = int(os.getenv("GROUND_RECURSION_LIMIT", "12"))
GROUND_REACT_TRACE_ENABLED = os.getenv("GROUND_REACT_TRACE_ENABLED", "").lower() in {
    "1",
    "true",
    "yes",
}

RETRY_MAX = int(os.getenv("RETRY_MAX", "2"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.5"))


def live_models_enabled() -> bool:
    """Return whether model calls are explicitly available for this process.

    Tests and first-run local installs work offline. Production uses live models as
    soon as an OpenAI key is present, unless the user explicitly sets AGENT_OFFLINE.
    """

    return bool(llm_api_key()) and os.getenv("AGENT_OFFLINE", "").lower() not in {
        "1",
        "true",
        "yes",
    }
