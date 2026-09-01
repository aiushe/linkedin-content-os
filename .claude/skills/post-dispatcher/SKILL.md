---
name: post-dispatcher
description: Preview and dispatch an approved draft to LinkedIn via Apify with human confirmation.
---

# Post dispatcher

1. Run `uv run python pipeline/dispatch.py list` to show queued drafts with their
   claims/voice/confidential verdicts.
2. Let the user pick a draft (or use the one they specified).
3. Run `uv run python pipeline/dispatch.py preview --draft <path>` and display the full text,
   hook variants, and observation flags.
4. Highlight any warnings: unresolved claims, voice flags, confidential-term matches.
   These are informational — they do not block dispatch.
5. Ask the user: "Ready to dispatch this to LinkedIn?" Do not proceed without explicit yes.
6. On confirmation: `uv run python pipeline/dispatch.py send --draft <path> --confirm --allow-network`.
7. Report the result: published file path and dispatch timestamp, or error details.

Requires `APIFY_API_TOKEN`, `LINKEDIN_LI_AT_COOKIE`, and `APIFY_POST_ACTOR_ID` in `.env`.
The daily dispatch limit defaults to 3; override with `DISPATCH_DAILY_LIMIT` in `.env`.
