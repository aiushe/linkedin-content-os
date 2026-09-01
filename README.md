# LinkedIn Content OS

A local-first collaborative drafting system for LinkedIn. Give it a rough thought, a story from
your career, or a target role — it drafts content grounded in your verified experience, checks it
against deterministic voice/claims/confidential gates, and lets you iterate in plain language.
Everything is advisory. The user always decides.

Nothing publishes, sends a message, or writes personal information automatically.

## What it does

- **Story-grounded drafting:** Retrieves verified stories and truth-table facts as evidence.
  Optional market context provides structure inspiration, never factual claims.
- **Deterministic claim detection:** Finds numeric, superlative, and attribution claims and
  matches them against your truth-table allowlist. Each report includes span, kind, sentence,
  and line number.
- **Voice fingerprinting:** Measures word count, contraction rate, first-person rate, hedge words,
  and opening-move patterns. Compares drafts against your published samples.
- **Confidential-term scanning:** Advisory detection of employer-sensitive terms. Warns but
  never blocks.
- **Iterative drafting:** Keeps prior drafts and every user direction in context. A newer
  direction wins only when it conflicts with an older one.
- **Source recording:** Lets you record a source with exact claim, proof, date, and verification
  text — the only private-corpus write.
- **Queue with full provenance:** Saves approved drafts to `drafts/queue/` with the claims,
  voice, confidentiality, market, and degradation observations present at save time.
- **Human-gated dispatch:** Publishes approved drafts to LinkedIn via Apify with explicit
  confirmation, daily rate limits, and cookie security.

## Quick start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv) (Python package manager)
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (for skill-based workflows)

### Installation

```bash
git clone <repo-url> && cd linkedin-content-os
uv sync --extra dev
cp .env.example .env   # then fill in your keys
```

### Configure `.env`

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Yes | LLM provider for drafting and routing |
| `APIFY_API_TOKEN` | For scraping/dispatch | Apify actor calls (market intel + posting) |
| `LINKEDIN_LI_AT_COOKIE` | For dispatch | Session cookie for posting (browser DevTools > Application > Cookies > `li_at`) |
| `APIFY_POST_ACTOR_ID` | No | Posting actor (default: `curious_coder/linkedin-auto-poster`) |
| `DISPATCH_DAILY_LIMIT` | No | Max posts per day (default: 3) |
| `MEM0_API_KEY` | No | Optional profile memory across sessions |
| `EMBED_PROVIDER` | No | Embedding provider (default: `openai`) |

See `.env.example` for the full list including LLM provider overrides, LangSmith tracing,
and scraper defaults.

### Populate your corpus

```bash
# Copy tracked templates to the ignored private directory
cp -r corpus/identity/ private/identity/
cp -r corpus/stories/ private/stories/
# Edit private/ files with your real data — never commit them
```

### Build local indexes

```bash
uv run python pipeline/index_corpus.py
uv run python pipeline/voice.py fingerprint
uv run python pipeline/cluster.py text
uv run python scripts/build_reports.py
```

### Run the studio (Streamlit UI)

```bash
uv run streamlit run app.py
```

### Run through Claude Code (recommended)

Open Claude Code in the project directory. All capabilities are available as slash commands:

```
claude
```

Then type any skill command (see [Skills](#skills) below).

## Skills

Every workflow is a Claude Code skill invoked with a slash command. Skills are instructions, not
evidence — they govern process and structure but never widen the factual allowlist.

### Content creation

| Command | What it does |
|---|---|
| `/authority-post` | Draft a grounded first-person post showing how you think and work |
| `/reach-post` | Draft a broader useful post while retaining evidence and voice gates |
| `/hook-lab` | Generate and rank 10 hook variants for a finished post body |
| `/voice-check` | Gate a draft with deterministic stylometry and sample-based editorial check |
| `/image-brief` | Create a paste-ready image generation brief for a reviewed post |
| `/post-templatizer` | Extract reusable structure from a high-performing post |

### Profile and job search

| Command | What it does |
|---|---|
| `/jd-keyword-miner` | Mine 5+ job descriptions into a focused role-keyword brief |
| `/profile-rewriter` | Rewrite your LinkedIn profile using only verified evidence |
| `/target-mapper` | Build a manual people-map for an applied-to target role |

### Engagement and curation

| Command | What it does |
|---|---|
| `/comment-drafter` | Draft substantive comments for researched target professionals |
| `/story-bank-curator` | Turn career conversations into reviewable story-bank entries |

### Publishing

| Command | What it does |
|---|---|
| `/post-dispatcher` | Preview queued drafts, show observation flags, and dispatch to LinkedIn with explicit confirmation |

## Architecture

### Directory layout

```
linkedin-content-os/
├── .claude/skills/          # 12 Claude Code skill definitions
├── agent/                   # LangGraph workflow (graph, nodes, gates, tools)
│   ├── graph.py             # State machine: memory → route → ground → write → gate → critique → HITL → commit
│   ├── nodes/               # 10 workflow nodes (router, ground, write, gate, critique, hitl, commit, memory, outreach, profile_rewrite)
│   ├── gates.py             # Voice fingerprint scorer, advisory verdict reduction
│   ├── tools.py             # Read-only LangChain tools
│   └── config.py            # Model timeouts, recursion limits, provider setup
├── pipeline/                # Deterministic data processing (no LLM calls)
│   ├── claims.py            # Claim extraction and truth-table matching
│   ├── voice.py             # Voice fingerprinting and scoring
│   ├── confidential.py      # Advisory confidential-term detection
│   ├── dispatch.py          # Human-gated LinkedIn post dispatch via Apify
│   ├── scrape.py            # Explicit opt-in Apify actor wrapper
│   ├── pull_profile.py      # LinkedIn profile scraper
│   ├── normalize.py         # Raw actor payload → canonical post records
│   ├── embed.py             # Text/image embeddings with content-hash caching
│   ├── cluster.py           # Post clustering by embedding + structure
│   ├── xfactor.py           # Engagement x-factor computation
│   ├── selfmetrics.py       # Own-post performance reporting
│   ├── index_corpus.py      # Transparent metadata index over story bank
│   └── common.py            # Shared helpers (paths, JSON I/O, frontmatter parsing)
├── mcp/server.py            # FastMCP read-only tool surface
├── app.py                   # Streamlit studio UI
├── corpus/                  # Tracked templates (identity, stories, targets, profile)
├── private/                 # Ignored personal corpus (your real data)
├── intel/                   # Disposable market research (posts, embeddings, vectors)
├── drafts/                  # Draft lifecycle: queue → approved → published
├── ops/                     # Operational logs (engagement queue, outreach, metrics, dispatch log)
├── scripts/                 # Admin scripts (audit, reports, model probing)
├── evals/                   # Fixture evaluation suite
└── tests/                   # 139 tests across 28 files
```

### Draft lifecycle

```
Idea / rough thought
      |
      v
[Router] ─── classify intent (authority, reach, comment, profile_rewrite, outreach)
      |
      v
[Ground] ─── retrieve stories, truth-table, market context, templates
      |
      v
[Write] ──── draft with voice rules + 5 hook variants
      |
      v
[Gate] ───── deterministic checks: voice, claims, confidential (advisory only)
      |
      v
[Critique] ─ observations and suggestions (no automatic revisions)
      |
      v
[HITL] ────── human decision: approve / edit / feedback / source / reject
      |
      v
[Commit] ──── save to drafts/queue/ with full observation snapshot
      |
      v
[Dispatch] ── /post-dispatcher: preview → confirm → publish to LinkedIn
```

### Data pipelines

| Pipeline | Input | Output | LLM? |
|---|---|---|---|
| `claims.py` | Draft text + truth table | Grounded/ungrounded claim report | No |
| `voice.py` | Draft text + voice samples | Fingerprint scores + tell flags | No |
| `confidential.py` | Draft text + term list | Advisory match report | No |
| `normalize.py` | Raw Apify payload | Canonical post records | No |
| `embed.py` | Post/story text | Vectors + content-hash cache | Yes (embedding API) |
| `cluster.py` | Post embeddings | Structural clusters + templates | No |
| `xfactor.py` | Post engagement stats | Per-author x-factor scores | No |
| `dispatch.py` | Approved draft | Published draft + dispatch log | No |

### Safety model

All checks are **advisory** — they inform the user but never block, escalate, or auto-rewrite:

- **Claims gate:** Extracts numeric/superlative/attribution claims and matches against the
  truth-table allowlist. Unresolved claims are flagged, not removed.
- **Voice gate:** Runs deterministic stylometry. Flags tells that make the draft sound unlike
  published samples.
- **Confidential gate:** Warns about employer-sensitive terms. The git boundary (not this check)
  keeps drafts private.
- **Dispatch gate:** Requires `--confirm` and `--allow-network`. Enforces daily rate limit.
  Cookie never written to logs or disk.

## Market intelligence

Scrape LinkedIn posts from your watchlist for structure and engagement analysis:

```bash
# Pull posts from watchlist profiles (requires APIFY_API_TOKEN)
uv run python pipeline/scrape.py --input private/targets/watchlist.json --allow-network

# Normalize raw payloads to canonical format
uv run python pipeline/normalize.py --my-handle your-handle

# Build embeddings and clusters
uv run python pipeline/embed.py
uv run python pipeline/cluster.py text

# Generate reports
uv run python scripts/build_reports.py
```

Results land in `intel/` (ignored) and `intel/reports/` (tracked).

## Verification

```bash
uv run pytest -q                          # 139 tests
uv run ruff check . --exclude .venv       # linter
uv run python scripts/audit.py            # repo health, queue validation, data stats
uv run python evals/run.py                # fixture eval: claim recall, clean precision, delivery
```

The fixture evaluation reports planted-claim recall, precision on clean drafts (including
hyphenated-compound cases), and draft delivery to the user. It does not report refusal-oriented
safety or containment rates.

## Privacy and evidence boundaries

| Directory | Tracked | Purpose |
|---|---|---|
| `private/` | No (ignored) | Personal corpus: identity, stories, JDs, targets, profile |
| `corpus/` | Yes | Templates for identity, stories, targets, profile structure |
| `intel/` | No (ignored, except `reports/`) | Disposable market research, embeddings, vectors |
| `drafts/` | No (ignored) | Queue, approved, published drafts |
| `ops/` | No (ignored) | Engagement queue, outreach log, metrics, dispatch log |
| `.env` | No (ignored) | API keys, cookies, credentials |
| `tests/fixtures/` | Yes | Fictional dev corpus for repeatable testing |

Mem0 profile memory is optional, non-evidentiary context. It never creates a claim or expands
the allowlist. If LangSmith tracing is enabled, memory stays out of model prompts until
separately approved with `MEM0_ALLOW_LANGSMITH_TRACING=true`.

See [docs/architecture.md](docs/architecture.md) for the full workflow specification.
