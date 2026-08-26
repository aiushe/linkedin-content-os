# LinkedIn Content OS

A local, human-gated system for turning your real career stories and market research into
better LinkedIn profile copy, posts, and outreach. It never publishes, messages, or invents
claims on your behalf.

## Quick start

1. Install Python 3.11+ and [uv](https://docs.astral.sh/uv/), then run `uv sync --extra dev`.
2. Copy `.env.example` to `.env`; only add external keys when you reach those phases.
3. Fill the templates in `corpus/identity/`, paste your profile into
   `corpus/profile/current.md`, and add stories via `corpus/stories/_TEMPLATE.md`.
4. Add five target job descriptions to `corpus/targets/jds/`, then follow the
   `jd-keyword-miner` skill.
5. Run `uv run python pipeline/index_corpus.py` whenever stories change and
   `uv run python pipeline/voice.py fingerprint` when you have writing samples.

`PLAN.md` is the product plan. The system is deliberately useful before any scraping or
embedding credentials are configured: metadata-based story retrieval, JD mining, voice
statistics, and x-factor calculations all run locally.

## Safety boundary

All output is a review artifact. Only you publish posts, make comments, or send DMs.
