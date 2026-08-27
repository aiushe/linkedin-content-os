# LinkedIn Content OS

A local, human-gated system for turning your real career stories and market research into
better LinkedIn profile copy, posts, and outreach. It never publishes, messages, or invents
claims on your behalf.

## Quick start

1. Install Python 3.12 and [uv](https://docs.astral.sh/uv/), then run `uv sync --extra dev`.
2. Add an `OPENAI_API_KEY` to your existing local `.env` only when you want live model calls;
   the test suite and fixture evals run offline.
3. Put personal material in the ignored `private/` folder: copy the identity templates from
   `corpus/identity/`, paste your profile into `private/profile/current.md`, and add stories
   using `corpus/stories/_TEMPLATE.md` as the format.
4. Add five target job descriptions to `private/targets/jds/`, then follow the
   `jd-keyword-miner` skill.
5. Run `uv run python pipeline/index_corpus.py` whenever stories change and
   `uv run python pipeline/voice.py fingerprint` when you have writing samples.

`PLAN.md` is the product plan. The system is deliberately useful before any scraping or
embedding credentials are configured: metadata-based story retrieval, JD mining, voice
statistics, and x-factor calculations all run locally.

## Week 3 harness

The LangGraph harness turns a rough idea into a grounded draft, runs deterministic
voice and factual gates, and pauses for six human review actions before the sole
write to `drafts/queue/`.

```bash
uv run pytest
uv run python evals/run.py
uv run streamlit run app.py
```

See [architecture.md](docs/architecture.md) for the graph, failure policy, and
the real-corpus handoff. The tracked `tests/fixtures/dev_corpus/` is fictional;
it is intentionally separate from the ignored `private/` corpus.

## Safety boundary

All output is a review artifact. Only you publish posts, make comments, or send DMs.
