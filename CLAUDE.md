# LinkedIn Content OS

This repository is a personal collaborative drafting system. Treat `private/` as the personal
source of truth, `corpus/` as tracked templates, and `intel/` as disposable market research.

## Non-negotiable rules

1. Do not invent, infer, or pre-fill factual content. When information is needed, ask the user.
   Keep every detected claim, voice difference, and confidential match intact in the report.
2. Do not write in `private/` except when the user explicitly records a source. In that case,
   append only the exact claim, proof, date, and verification text the user entered to
   `private/identity/truth-table.md`.
3. Checks are informational. They never block a draft, trigger escalation, or cause an automatic
   rewrite. The user always sees a draft and decides what to do with it.
4. User directions are the highest-priority writer input. Preserve prior directions and the prior
   draft through a conversation; let a later instruction override an earlier one only if they
   conflict. Computed observations are commentary, not writer control flow.
5. Saving is a user action and is always available from the review surface. A saved queue draft
   records its full observation snapshot: grounded and ungrounded claims, voice,
   confidential-term, market, and degradation context.
6. Nothing publishes automatically. Do not send messages, record outreach activity, or ingest
   private corpus content into external services. Keep `private/`, drafts, and generated market
   data out of git.
7. Do not put `#` comments on command lines; interactive zsh treats them specially.

## Primary inputs

- Personal positioning, ICP, pillars, verified claims, voice, stories, profile, and target
  material: `private/` (ignored; never stage it).
- Tracked templates and generic playbooks: `corpus/`.
- Market posts and reports: `intel/`.

## Local verification

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check . --exclude .venv
uv run python scripts/audit.py
uv run python evals/run.py
```

The fixture suite measures detector recall for planted ungrounded claims, precision on clean
drafts (including hyphenated compounds), and whether the user received a draft. It does not use
refusal, containment, or safety rates.
