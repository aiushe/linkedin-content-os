"""Central configuration for the agent harness.

Keep data-dependent thresholds here so corpus seeding changes configuration rather
than graph logic.
"""

from __future__ import annotations

import os

ROUTER_CONFIDENCE_FLOOR = float(os.getenv("ROUTER_CONFIDENCE_FLOOR", "0.70"))
VOICE_Z_THRESHOLD = float(os.getenv("VOICE_Z_THRESHOLD", "1.5"))
VOICE_MIN_SAMPLES = int(os.getenv("VOICE_MIN_SAMPLES", "3"))
VOICE_MIN_WORDS = int(os.getenv("VOICE_MIN_WORDS", "1500"))
MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "3"))
CLAIM_REQUIRE_EXACT = True

MODEL_ROUTER = os.getenv("MODEL_ROUTER", "gpt-4o-mini")
MODEL_WRITER = os.getenv("MODEL_WRITER", "gpt-4.1")
MODEL_CRITIC = os.getenv("MODEL_CRITIC", "gpt-4o-mini")

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
