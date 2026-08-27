# LinkedIn Content OS

This repository is a personal, human-gated content and job-search system. Treat
`private/` as the personal source of truth, `corpus/` as tracked templates, and `intel/` as
disposable market research.

## Non-negotiable rules

1. Nothing publishes automatically. Drafts and engagement suggestions only ever go to
   `drafts/queue/` or `ops/` for a human to review.
2. Do not state a factual claim unless it appears in `private/identity/truth-table.md` (or the
   tracked template before private data exists) or in a
   retrieved story with a verified metric. Unverified metrics may be discussed as narrative,
   never as numbers.
3. Preserve the user's actual voice. Run `pipeline/voice.py score` and the `voice-check`
   skill before queuing a draft. Do not use a generic "professional LinkedIn" voice.
4. Keep `private/` and generated market data out of git. Do not scrape LinkedIn with a personal session
   cookie. Review an actor's terms, pricing, and proxy behavior before using it.

## Primary inputs

- Personal positioning, ICP, pillars, verified claims, voice, stories, profile, and target
  material: `private/` (ignored; never stage it).
- Tracked templates and generic playbooks: `corpus/`.
- Market posts and reports: `intel/`

## Skills

- `jd-keyword-miner`: turn a focused set of JDs into a keyword brief; halt if it is scattered.
- `profile-rewriter`: make a recruiter-readable, truthful profile.
- `post-templatizer`, `authority-post`, `reach-post`, `hook-lab`, `image-brief`: draft only.
- `voice-check`, `story-bank-curator`: protect voice and improve the source corpus.
- `target-mapper`, `comment-drafter`: provide manual outreach support; never send/post.

## Local commands

```bash
uv sync --extra dev
uv run python pipeline/index_corpus.py
uv run python pipeline/voice.py fingerprint
uv run python pipeline/xfactor.py
uv run python pipeline/normalize.py --input intel/raw/pull.json
uv run pytest
```
