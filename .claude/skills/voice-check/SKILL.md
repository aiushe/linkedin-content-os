---
name: voice-check
description: Gate drafts with deterministic stylometry and a sample-based editorial check.
---

# Voice check

Before a draft reaches `drafts/queue/`:

1. Run `python pipeline/voice.py score <draft>`.
2. Fix banned tells and explain any remaining numeric fingerprint flags.
3. Compare the draft with five relevant files in `private/identity/voice/samples/` or
   `exemplars/`. Identify the concrete tell that makes it sound unlike the same author.
4. Revise up to three times. If it still fails, save it with `voice_check: flagged` and list
   the unresolved tell; do not silently treat it as passing.

Use mode-specific rules: profile copy, posts, comments, and DMs should not share a single
register. Feed published-vs-generated pairs to `pipeline/voicediff.py`; promote a rule only
after the same directional edit occurs at least three times.
