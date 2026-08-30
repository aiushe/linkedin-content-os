# LinkedIn Content OS

LinkedIn Content OS is a local collaborative drafting tool. Give it a rough thought or draft;
it creates one LinkedIn draft, shows what it could ground and what it could not, then lets you
iterate in plain language. The checks are advisory. The user decides whether to revise, record a
source, save, or stop.

## What it does

- Retrieves local verified stories and truth-table facts as evidence, with optional market context
  for structure only.
- Detects numeric, superlative, and attribution claims without weakening the detector; each
  report includes the span, kind, sentence, and line number.
- Reports voice differences and confidential-term matches as readable observations, never a
  refusal or automatic revision.
- Keeps prior drafts and every user direction in the writer context. Directions persist for a
  conversation; a newer direction wins only when it conflicts with an older one.
- Lets the user record a source with exact claim, proof, date, and verification text. That is the
  only private-corpus write, and it appends only the entered values to the private truth table.
- Saves any user-approved draft to `drafts/queue/`, including the claims, voice,
  confidentiality, market, and degradation observations present at save time.

Nothing publishes, sends a message, or writes personal information automatically.

## Quick start

1. Install Python 3.12 and [uv](https://docs.astral.sh/uv), then run `uv sync --extra dev`.
2. Populate the ignored `private/` corpus from the tracked `corpus/` templates. Never commit it.
3. Refresh local evidence after corpus changes:

   ```bash
   uv run python pipeline/index_corpus.py
   uv run python pipeline/voice.py fingerprint
   uv run python pipeline/cluster.py text
   uv run python scripts/build_reports.py
   ```

4. Run the studio:

   ```bash
   uv run streamlit run app.py
   ```

For live models, configure `LLM_BASE_URL`, `LLM_API_KEY_ENV`, the corresponding key variable,
and selected router/writer/critic models in your untracked `.env`.

## Verify

```bash
uv run pytest -q
uv run ruff check . --exclude .venv
uv run python scripts/audit.py
uv run python evals/run.py
```

The fixture evaluation reports planted-claim recall, precision on clean drafts (including
hyphenated-compound cases), and draft delivery to the user. It does not report refusal-oriented
safety or containment rates.

## Privacy and evidence boundaries

`private/` is the ignored personal corpus; `corpus/` holds tracked templates; `intel/` contains
disposable market research. Mem0 profile memory is optional, non-evidentiary context and never
creates a claim or expands the allowlist. If LangSmith tracing is enabled, memory stays out of
model prompts until separately approved with `MEM0_ALLOW_LANGSMITH_TRACING=true`.

See [architecture.md](docs/architecture.md) for the workflow, advisory observations, source
recording, iteration behavior, and saved-draft provenance.
