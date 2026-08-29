# LinkedIn Content OS

A local, human-gated LangGraph system for grounded LinkedIn drafting. It uses
your ignored `private/` corpus for evidence and voice analysis, optional market
intel for structural context, and deterministic voice and factual-claim gates.
Nothing is published, messaged, or written to `drafts/queue/` without an
`interrupt()` approval.

## Current capabilities

- Routes authority, reach, comment, profile-rewrite, outreach, and out-of-scope
  requests.
- Loads authored role playbooks from `.claude/skills/` into writer and critique
  prompts without allowing them to override factual evidence or a gate.
- Stops profile rewriting if JD keyword coverage is below 0.75.
- Provides read-only outreach guidance only after the user records that an
  application was submitted; it never records an account or person automatically.
- Uses Nebius Token Factory through its OpenAI-compatible API for live models.
- Treats market intel as structural context, never as evidence for a factual claim.

## Quick start

1. Install Python 3.12 and [uv](https://docs.astral.sh/uv), then run
   `uv sync --extra dev`.
2. Populate the ignored `private/` corpus from the tracked `corpus/` templates.
   Never commit that material.
3. Build the local indexes after corpus changes:

   ```bash
   uv run python pipeline/index_corpus.py
   uv run python pipeline/voice.py fingerprint
   ```

4. For live Nebius calls, configure local `.env` values for `LLM_BASE_URL`,
   `LLM_API_KEY_ENV`, the corresponding API-key variable, and the selected
   router, writer, and critic models. Keep all credentials out of tracked files.
5. Optionally enable LangSmith dashboard traces with `LANGSMITH_TRACING=true`,
   `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`. Traces export prompts and
   outputs to LangSmith, so enable them only with approval for that data flow.

## Verify and run

```bash
uv run pytest -q
uv run ruff check agent pipeline evals tests scripts
AGENT_OFFLINE=0 uv run python evals/run.py
uv run streamlit run app.py --server.headless true
```

The tracked `tests/fixtures/dev_corpus/` is fictional. The evaluation reports
prevention, deterministic-gate defense, and containment separately so a writer
that declines to fabricate is not scored as a failure.

## Safety boundary

All output is a review artifact. Only the human user publishes posts, makes
comments, sends messages, or approves a queue write. See
[architecture.md](docs/architecture.md) for the graph, failure policy, market
intel boundary, and current configuration.
