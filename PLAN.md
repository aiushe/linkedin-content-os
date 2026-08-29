# LinkedIn Content OS — Historical Build Plan

> **Status: implemented and superseded as an execution plan (2026-08-28).**
> This file preserves the original design rationale and phased plan. It is not
> the current architecture or operational guide. The implemented system uses
> an ignored `private/` corpus, Nebius Token Factory, LangGraph, deterministic
> voice and claim gates, market-template retrieval, authored skill injection,
> profile-rewrite coverage halting, read-only outreach guidance, and a required
> human interrupt before a queue write. See `docs/architecture.md` for the
> current system, `README.md` for setup, and `NEXT_INPUTS.md` for open decisions.

A personal content + job-search operating system, modeled on the system described in
`transcript.txt` (Basha Kubitzka on Akash's podcast), rebuilt as a proper engineering
project with a retrieval layer, an intelligence pipeline, an MCP surface, and
human-gated agentic automation.

**Starting state:** empty repo, brand-new LinkedIn posting habit.
**Goal state:** a profile that converts recruiter/HM attention into DMs, and a repeatable
3-posts-a-week engine grounded in your real stories and in what demonstrably works.

---

## 0. Design thesis

The transcript describes three components (profile / content / active networking) and one
non-obvious insight: **the reason it runs in Claude Code rather than Claude chat is that the
system needs persistent, retrievable memory of who you are** — the "story bank," the ICP doc,
the positioning. Everything else is prompting.

So the architecture centers on that:

```
                    ┌─────────────────────────────────────────┐
                    │           corpus/  (YOUR TRUTH)         │
                    │  identity · stories · profile · targets │
                    └──────────────────┬──────────────────────┘
                                       │ indexed
                    ┌──────────────────▼──────────────────────┐
   Apify ──scrape──►│      intel/  (MARKET TRUTH)             │
   (LinkedIn,       │  posts · x-factor · embeddings · clusters│
    X, Substack)    └──────────────────┬──────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────┐
                    │        mcp/server.py  (typed tools)     │
                    │  search_stories · find_viral_posts ·    │
                    │  similar_images · truth_table · log_story│
                    └──────┬────────────────────────┬─────────┘
                           │                        │
              ┌────────────▼─────────┐   ┌──────────▼───────────┐
              │ .claude/skills/      │   │ Claude Desktop /     │
              │ (the playbook, as MD)│   │ mobile (draft on go) │
              └────────────┬─────────┘   └──────────┬───────────┘
                           │                        │
                           └────────►  drafts/ + ops/ (you edit, you publish)

              everything runs when YOU start a session. no cron.
```

Two design rules that everything else obeys:

1. **Nothing publishes itself.** Every agent writes a draft to `drafts/` or `ops/` for you to
   approve. The transcript is explicit that Claude produces "only the first draft" and the
   human pass — especially on hooks — is what makes it work.
2. **The writer can only assert what retrieval returns.** Profile and post skills may only
   state facts that come back from `corpus/identity/truth-table.md` or a retrieved story.
   This is the anti-fabrication guard, and it directly implements the transcript's
   "which of these can you truthfully claim?" step.

---

## 1. Repo layout

**Decision: one repo.** Her setup was two — Claude Code skills in VS Code, plus a separate
vibe-coded localhost research app. We're merging them, because in our design the intel layer
has no UI of its own: it's JSON that the skills read directly. A second project would exist
only to hold files this one already needs. If the dashboard gets built later (§Phase 3, UI
deferred), it lives here too, as a thin read view over `intel/posts/*.json`.


```
linkedin-content-os/
├── CLAUDE.md                     # harness: rules, corpus pointers, voice constraints
├── PLAN.md                       # this file
├── .env.example
├── pyproject.toml
│
├── .claude/
│   ├── settings.json             # permissions, MCP server registration
│   └── skills/
│       ├── jd-keyword-miner/SKILL.md
│       ├── profile-rewriter/
│       │   ├── SKILL.md
│       │   └── references/
│       │       ├── recruiter-lens.md      # "the skill has the eyes of the recruiter"
│       │       ├── niche-definition.md    # domain / product type / superpower / stage
│       │       ├── tagline-patterns.md
│       │       ├── about-patterns.md
│       │       ├── experience-patterns.md
│       │       └── edge-pass.md           # weakness → strength rewrite
│       ├── post-templatizer/SKILL.md
│       ├── authority-post/SKILL.md
│       ├── reach-post/SKILL.md
│       ├── hook-lab/SKILL.md
│       ├── voice-check/SKILL.md            # stylometry gate + LLM judge
│       ├── image-brief/SKILL.md
│       ├── story-bank-curator/SKILL.md
│       ├── target-mapper/SKILL.md         # JD → team → people
│       └── comment-drafter/SKILL.md
│
├── corpus/                       # hand-authored + Claude-interviewed. THE MOAT.
│   ├── identity/
│   │   ├── positioning.md        # one-paragraph "who I am, for whom"
│   │   ├── icp.md                # the deep ICP doc (see §4.2)
│   │   ├── pillars.md            # 3–5 brand pillars + why each maps to target roles
│   │   ├── truth-table.md        # every verified metric/claim, with proof + date
│   │   ├── voice.md              # fingerprint, rules, banned list, per-mode profiles
│   │   └── voice/
│   │       ├── samples/          # YOUR raw writing — slack, docs, emails, transcripts
│   │       ├── exemplars/        # the 3–5 pieces you're genuinely happy with
│   │       ├── negative/         # writing that isn't you + rejected AI drafts
│   │       └── edits/            # generated-vs-published diffs (the training signal)
│   ├── stories/                  # one story = one .md file with frontmatter
│   │   ├── _TEMPLATE.md
│   │   └── ...
│   ├── profile/
│   │   ├── current.md            # scraped/pasted live profile, all sections
│   │   └── versions/YYYY-MM-DD-vN.md
│   └── targets/
│       ├── jds/                  # raw job descriptions
│       ├── briefs/               # keyword briefs from the miner
│       └── companies/            # per-company people maps
│
├── intel/                        # market intelligence (derived, disposable, rebuildable)
│   ├── posts/                    # one JSON file per pull: {date}-{actor}.json
│   ├── raw/                      # raw Apify JSON, dated
│   ├── images/                   # downloaded post images for multimodal embedding
│   └── reports/                  # top-posts.md, template-library.md
│
├── pipeline/
│   ├── scrape.py                 # Apify actors → intel/raw/
│   ├── normalize.py              # raw actor JSON → flat post records
│   ├── xfactor.py                # author baselines + per-post x-factor
│   ├── embed.py                  # Voyage text + multimodal embeddings
│   ├── cluster.py                # template + image-family discovery
│   ├── index_corpus.py           # embed corpus/stories → story index
│   ├── voice.py                  # stylometric fingerprint + draft scoring
│   ├── voicediff.py              # mine generated-vs-published diffs into rules
│   └── selfmetrics.py            # scrape your own posts, compute your own x-factor
│
├── mcp/
│   └── server.py                 # FastMCP server exposing corpus + intel
│
├── drafts/
│   ├── queue/                    # agent-generated, unreviewed
│   ├── approved/                 # you edited + signed off
│   └── published/                # with post URL + performance snapshot
│
└── ops/
    ├── engagement-queue.md       # today's comment targets + drafted comments
    ├── outreach-log.md           # who you DM'd, which script, outcome
    └── metrics/                  # your own x-factor over time
```

**Rationale for the corpus/intel split:** `corpus/` is irreplaceable and git-tracked;
`intel/` is derived and rebuildable, so it's gitignored except reports. Losing `intel/`
costs you a scrape run. Losing `corpus/` costs you the whole system.

---

## 2. Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ (via `uv`) | System python here is 3.9; `uv` pins a project-local interpreter |
| Store | **Plain JSON files.** No database | See §3.0. A full watchlist refresh is ~1,200 posts / ~3 MB. Python dicts handle it. SQLite (stdlib) is the escalation path if cross-run querying ever gets annoying; DuckDB is not needed at any foreseeable scale here |
| Embeddings | Voyage `voyage-3` (text) + `voyage-multimodal-3` (images) | What the transcript uses; multimodal is the piece that enables "group by image" |
| Vector search | numpy brute force, vectors in a `.npy` file | 1,200 x 1024 floats is ~5 MB. Cosine over that is microseconds. No vector DB, no index |
| **LinkedIn connection (primary)** | **Apify MCP server + a LinkedIn scraper actor** | This is the LinkedIn pipe. Register the server, call the actor, get posts. Zero pipeline code — see §2.1 |
| Scraping (scale-up, later) | Apify REST/SDK from `pipeline/scrape.py` | Only if you outgrow driving it conversationally. Re-pulling costs ~$2, so there is no checkpointing to build |
| Agent surface | Claude Code skills + `.claude/settings.json` | Skills are just `.md`, per transcript |
| Tool surface | MCP (FastMCP) | Same corpus reachable from Claude Desktop/mobile for drafting away from the laptop |
| Images | ChatGPT / image model, driven by a generated brief | Transcript uses ChatGPT + dictation |

### 2.1 MCP surfaces — the standing dependency check

**Apify MCP is how this repo talks to LinkedIn.** There is no LinkedIn-specific MCP server
— that part of the transcript is still accurate — but Apify's Store contains LinkedIn scraper
actors, and Apify's official MCP server exposes those actors as callable tools. Register it,
point it at a LinkedIn actor, and Claude can pull posts directly. **That is the connection,
and it needs no code.**

> Note on sourcing: the transcript is audio of a screen-share, so her actual config was never
> spoken. She says only "I use Apify... different actors," which is consistent with either an
> SDK call or an MCP call. Treat MCP-vs-SDK as our engineering choice, not as something the
> transcript settles.

**Rule: for every external service in this stack, ask whether it already exposes an MCP
server before writing an integration.** This plan initially missed Apify's, because the
transcript frames Apify as *the thing you use since no LinkedIn MCP exists* — easy to carry
that framing forward and never ask the separate question. Run the sweep deliberately.

| Server | Status | Exposes | Called by | Use for |
|---|---|---|---|---|
| **Apify MCP** ⭐ | official, hosted + package | Actor search, input schemas, **run LinkedIn scraper actors**, fetch dataset | You + skills | **The LinkedIn connection.** Profile pulls, creator watchlist, post scraping, ad-hoc research |
| **`mcp/server.py`** (ours) | to build, Phase 4 | `search_stories`, `find_viral_posts`, `similar_images`, `get_truth_table`, `log_story` | Skills, Claude Desktop/mobile | Everything the writer reasons over |
| **Google Drive** | already connected | Search/read Docs, Sheets, PDFs | You + `story-bank-curator` | Pull PRDs, post-mortems, strategy docs → voice samples + story raw material |
| **Gmail** | needs authorization | Read/search mail | You, one-time | Long emails are a **top-tier voice sample source** (§1.5.1) |
| **Google Calendar** | needs authorization | Events | You, one-time | Meeting history to jog story recall during the interview |
| LinkedIn | does not exist | — | — | The whole reason Apify is in this plan |
| Voyage | no MCP, and doesn't want one | — | `pipeline/embed.py` | Pure batch; an LLM in the loop adds nothing |

Gmail and Calendar require authorization through claude.ai connector settings before their
tools become callable. Drive is already live — which means the fastest path to a voice corpus
may be "search my Drive for docs I wrote," not "go export Slack."

**Start MCP-first; graduate to the SDK only when volume forces it.** MCP is for work where a
model is *reasoning* about what to call next — which is every scrape you do in weeks 1–4,
while you are still figuring out which creators matter and what the data looks like. Move a
job into `pipeline/scrape.py` only once you are tired of re-driving the same pull by hand,
where you need checkpoint-by-post-id, idempotent re-runs, and no tokens spent shuttling
thousands of rows through a context window. Until then, writing the pipeline is premature.

---

## 3. Data model

### 3.0 Why there is no database

Verified against [harvestapi/linkedin-profile-posts](https://apify.com/harvestapi/linkedin-profile-posts):

| Actor fact | Consequence |
|---|---|
| `maxPosts` per profile + `postedLimit` of `24h` / `week` / `month` | **One call returns the X-factor window.** `maxPosts=30, postedLimit='month'` gives the baseline and the outlier in the same response |
| Returns `engagement.likes / .comments / .shares` | Weighted engagement computable directly |
| No session cookie required | Matches the transcript: "You don't have to be logged into LinkedIn to use it" |
| ~$1.50–2 per 1,000 posts | 40 creators x 30 posts = 1,200 posts ~ **$2 per full refresh** |

So the workload is: pull ~1,200 posts (~3 MB of JSON), rank them, group them, read the top
ones. That is a Python list, not a database. **X-factor needs no stored history**, because
the window arrives inside the pull that contains the post being scored.

Two corollaries worth stating, since both were engineering I had planned and neither is needed:
- **No checkpointing.** Re-pulling everything costs about $2. Building incremental sync would
  cost more in effort than it ever saves.
- **No vector index.** Embeddings live in a `.npy` array beside the JSON; brute-force cosine
  over 1,200 vectors is microseconds.

Escalate to **SQLite** (stdlib, zero install) only if you later want cross-run trend queries —
"has this creator's baseline drifted over six months?" That is the first question JSON files
genuinely make awkward. DuckDB is not warranted at any scale this project is likely to reach.

### 3.1 Post record (`intel/posts/{date}-{actor}.json`)

```jsonc
{
  "id": "linkedin:7234...",
  "platform": "linkedin",
  "author_handle": "...", "author_name": "...", "author_info": "...",
  "url": "...", "posted_at": "2026-08-14T09:12:00Z", "scraped_at": "...",

  "text": "...",
  "hook": "first 3 lines, computed",
  "char_count": 1240,
  "media_type": "image",              // image | carousel | video | document | none
  "image_path": "intel/images/....jpg",

  "likes": 812, "comments": 94, "shares": 31,
  "engagement": 1249,                 // weighted, see §3.2
  "author_baseline": 201.4,           // mean of the other posts in this same pull
  "x_factor": 6.2,

  "funnel": "tofu",                   // LLM-classified, on demand
  "structure": { "hook": true, "bridge": true, "meat": true,
                 "micdrop": true, "cta": false },
  "template_id": 47,
  "image_family_id": 12,
  "is_mine": false
}
```

### 3.3 Your own performance — free, from the same pull

`targetUrls` accepts any public profile URL, including yours. So scoring your own posts needs
no separate mechanism:

```jsonc
{ "targetUrls": ["<your-profile>", "<creator-1>", "..."],
  "maxPosts": 30, "postedLimit": "month" }
```

Your posts come back in the same shape, get the same baseline treatment, and land in the same
ranked list flagged `is_mine: true`. You can read your X-factor against your watchlist's
directly — same metric, same window, one call.

**Template attribution is the one join the scrape cannot do.** The scraper knows a post
performed at 2.9x; it does not know you built it from template 47. That link lives in your own
files: when you publish, put the live post URL into the draft's frontmatter, and
`drafts/published/*.md` joins to the scraped record on URL. Then "which of my templates
actually beat my baseline" becomes answerable.

**Honest limit:** public scraping yields *engagement* (likes, comments, shares), never
*impressions*. LinkedIn shows impression counts only to you, in your own analytics, and there
is no API for them. So you can measure how hard a post landed with the people who saw it, not
how many people saw it. For choosing templates and hooks, engagement is the more useful signal
anyway — but do not mistake it for reach.

### 3.2 X-factor — computed per pull, no history required

The transcript: *"I look at the moving average of the last 30 posts for the last 30 days and
compare it to the latest post."* Three fixes worth making:

1. **Self-exclusion.** A viral post inflates its own baseline. Exclude the post under test.
2. **Weighted engagement,** not likes alone — comments are the stronger reach signal:
   `engagement = likes + 3*comments + 5*reposts`. (Keep `likes`-only as a config flag so you
   can reproduce her numbers.)
3. **Minimum sample.** If an author has <10 baseline posts in window, emit `NULL`, not a
   garbage ratio. Otherwise low-volume accounts dominate your "what works" list.

```
baseline(p) = mean(engagement of author's posts in [posted_at - 30d, posted_at), excluding p)
x_factor(p) = engagement(p) / baseline(p)        if n >= 10 else NULL
```

**Why this metric is the core of the whole intel layer:** it isolates *post quality* from
*audience size*. A 2,000-like post from a 200k-follower account teaches you nothing.
A 6× x-factor post from someone your size is a template worth stealing.

### 3.3 Story frontmatter (`corpus/stories/*.md`)

```yaml
---
id: shipped-payments-api-2024
title: Cut partner integration time from 6 weeks to 4 days
date: 2024-08
pillars: [apis, zero-to-one, developer-experience]
stage: 0-to-1                  # 0-to-1 | scaling | enterprise | public-co
role_context: PM, Payments Platform
metrics:
  - claim: "integration time 6 weeks → 4 days"
    proof: "internal onboarding dashboard, Q3'24 cohort"
    verified: true
tension: "Partners churned during onboarding before they ever hit production."
turn: "Realized the docs were the product, not the API."
result: "..."
lesson: "..."
emotions: [frustration, relief]
used_in: [drafts/published/2026-08-12-docs-are-the-product.md]
---

Full narrative in your own words...
```

The `verified` flag is what the writer skills check. Anything `verified: false` can be used
as *narrative* but never as a *number*.

---

## 4. Build phases

Ordered by ROI, not by architecture. **Phase 1 and 2 give you 80% of the value in week one** —
because you just started posting, your profile is what converts every visitor you earn, and
right now it's leaking.

---

### Phase 0 — Skeleton (½ day)

- `git init` already done; make the first commit.
- Create the directory tree, `pyproject.toml`, `.env.example`, `.gitignore`
  (ignore `intel/db`, `intel/raw`, `intel/images`, `.env`).
- Write `CLAUDE.md`: points at `corpus/identity/*`, states the two design rules from §0,
  and lists the skills. This file is the "harness" the transcript refers to.

**Deliverable:** repo that Claude Code can orient in.

---

### Phase 1 — Identity corpus (1–2 evenings) ⭐ HIGHEST LEVERAGE

This is the step the transcript calls step one, and the one most people skip.

**1.1 The story-bank interview.** Don't type stories cold. Run a session:
> "Interview me to build my story bank. Ask one question at a time. For each story I tell,
> extract tension → turn → result → lesson, push me for a specific number, and ask what
> proof I have for it. Write each as a file in corpus/stories/ using _TEMPLATE.md."

Target **15–25 stories** to start. The transcript's model is that it grows *situationally*
after that — every time you tell Claude a story while drafting, you end the session with
"add this to my story bank," which is what `story-bank-curator` automates.

**1.2 The ICP doc.** Per the transcript, in extreme detail — for a job seeker your ICP is the
hiring manager: who they are, their season of life, their fears, their pains, what they're
thinking but not saying, the exact words they use. Mine the *language* straight out of the
JDs you collect in Phase 2.

**1.3 Brand pillars (3–5).** Derived from the intersection of (a) what you've actually done
and (b) what your target JDs ask for. The transcript's own worked example: targeting API
platform roles → pillars become developer tools, customer discovery / 0-to-1, API pricing
and design. Add one personal pillar for range — the "don't be a flat personality" rule.
Test each pillar against: *does this look good to both my current and my future employer?*

**1.4 Truth table.** Every number you're allowed to claim, with proof and date. This is the
single most valuable file in the repo for keeping AI-drafted content honest.

**Deliverable:** `corpus/identity/` complete, `corpus/stories/` seeded.

---

### Phase 1.5 — Voice capture and enforcement (1 evening + ongoing) ⭐

Voice is where AI content systems most visibly fail, and it is **not** solved by a page
describing your tone. Models follow examples far better than they follow style adjectives.
So this is a subsystem with its own corpus, its own metrics, and its own feedback loop.

Three failure modes it exists to prevent:

1. **Description instead of demonstration.** "Direct, dry, concrete" produces generic prose
   that believes it is direct. Five real paragraphs of yours beat any adjective list.
2. **No negative signal.** Without an explicit banned list the model reaches for the same
   tells every time — rhetorical-question openers, `it's not X, it's Y`, tricolons,
   `here's the thing`, uniform paragraph lengths, fake-precise numbers.
3. **No feedback loop.** You edit every draft before publishing. That edit is the
   highest-quality training signal in the entire repo, and by default it is discarded.

#### 1.5.1 The sample corpus (`corpus/identity/voice/samples/`)

Do **not** build this mainly from LinkedIn posts — you have few, and it is your least
natural register. Better sources, in descending order of value:

| Source | Why it's good |
|---|---|
| Slack / Discord messages to colleagues | Unfiltered rhythm, real sentence lengths, actual vocabulary |
| Voice notes, transcribed | Spoken-you is usually much closer to good LinkedIn writing than written-formal-you. This is why the transcript's speaker dictates everything through Wispr Flow |
| Long, carefully-written emails | Your persuasive register |
| PRDs, design docs, post-mortems | Your thinking-out-loud register |
| Existing LinkedIn posts | Small but on-format |

Target **~5,000 words minimum, ~10,000 ideal**. Also collect a **negative set**:
writing that sounds nothing like you, plus any AI draft you rejected — annotated with *why*
you rejected it. The negative set does disproportionate work.

#### 1.5.2 `pipeline/voice.py` — a computed fingerprint

Extract objective, checkable features rather than adjectives:

- sentence-length **median and variance** (AI writes long *and uniform*; humans vary hard)
- paragraph-length distribution
- contraction rate, first-person rate, hedge-word rate
- punctuation profile (em-dash / semicolon / colon / parenthetical frequency)
- opening-move distribution — do you open on a scene, a claim, a number, or a question?
- type-token ratio, mean word length
- list usage: how often, how long, bulleted vs. prose

These become numeric targets, written into `voice.md` as a fingerprint block.

#### 1.5.3 `voice-check` skill — a two-stage gate, run before you ever see a draft

**Stage A — deterministic (cheap, instant).** Score the draft's stylometry against your
distribution. Flag any feature more than ~1.5σ off. Catches the obvious drift: sentences
too long and too even, contractions stripped, hedging elevated, paragraphs suspiciously equal.

**Stage B — LLM judge (the one that actually works).** Hand a judge model 5 of your real
samples plus the draft and ask: *which one was not written by the same person, and name the
specific tell.* The value is that it returns something actionable — "paragraphs 2 and 4 use a
parallel triple; the author never does that" — which the writer can then revise against.
Loop 2–3 times, all before the draft reaches `drafts/queue/`.

> **Design note — a technique to deliberately skip.** Embedding-similarity to a centroid of
> your writing looks like the obvious approach and largely does not work here: embeddings
> encode *topic* far more strongly than *style*, so any draft about your actual subject
> scores well regardless of voice. Stylometry + judge is the combination that earns its cost.

#### 1.5.4 The edit-diff loop — the part that compounds

When a draft moves `drafts/queue/` → `drafts/published/`, `pipeline/voicediff.py` diffs
generated against published and mines the delta for rules:

```
EDIT ANALYSIS · 2026-09-01-taxonomy-not-model

  You cut 5 of 5 rhetorical-question openers this month.
  → RULE: never open on a question.              (confidence: high, n=5)

  You replaced "leverage" 3x with "use"; also killed "utilize",
  "robust", "seamless".
  → BANNED, appended to voice.md

  Generated mic drop median 4 lines; published median 2.
  → CONSTRAINT: mic drop <= 2 lines

  You add a concrete number to paragraph 1 in 7 of 9 posts.
  Drafts do this in 2 of 9.
  → RULE: lead with a specific figure

  Proposed voice.md patch attached. Accept? (y/n)
```

Rules are only promoted after they appear **n>=3 times** with consistent direction — one
edit is noise, three is a pattern.

**Convergence is measurable.** Track mean edit distance (generated → published) per post.
It should fall noticeably by post ~10–15. If it doesn't, the sample corpus is too small or
too unlike your target register, and that is a diagnosable problem rather than a vibe.

#### 1.5.5 Modes

You do not have one voice. `voice.md` carries separate profiles for **post**, **comment**,
**profile-copy**, and **DM**. A comment written in your About-section register reads as a bot;
an About section written in comment register reads as unserious. Each mode gets its own
fingerprint and its own exemplars.

#### 1.5.6 Honest limitation

The first 5–10 posts still need real editing. There is no cold-start shortcut: the system
begins by imitating your samples and only becomes genuinely *yours* once the edit loop has
data. What it does guarantee from day one is the absence of the tells — no `delve`, no
`it's not X, it's Y`, no fake-precise numbers, no three-item lists where you would have
written two.

**Deliverable:** `voice.md` with a fingerprint, a starting rule set, a banned list, and
per-mode exemplars; `voice-check` gating every draft.

---

### Phase 2 — Profile pipeline (week 1)

**2.1 `jd-keyword-miner` skill.** Steps, exactly as the transcript describes them:
gather JDs → extract terms into categories → normalize and rank by coverage →
**diagnose focus and HALT if scattered** → emit keyword brief.

The halt condition is the load-bearing part. Implement it as a hard gate:

```
coverage = (# terms appearing in >= 4 of 5 JDs) / (# distinct significant terms)
if coverage < 0.75:
    STOP. Report the two or three distinct role clusters found.
    Tell the user to pick one and re-run. Do not write a profile.
```

Brief output sections: keywords by category with frequency across JDs; skills to list;
verbatim phrases to reuse; what these roles actually want; **gaps to flag**; final brief.

**2.2 `profile-rewriter` skill + reference files.** The reference files are where you encode
domain knowledge the model doesn't have — the transcript's insight is that Claude knows
generic hiring, not *your industry's* hiring managers. Encode:

- `recruiter-lens.md` — the three ICP journeys (content→tagline→profile; your comment→tagline→profile;
  boolean recruiter search→tagline→profile), and the conclusion that the tagline is the
  common denominator of all three.
- `niche-definition.md` — the four axes: domain, product type, superpower, company stage.
- `tagline-patterns.md` — role+specialty → 3 keywords → one hard result. Length cap
  (the transcript's live critique of Claude's output was "this is too long").
- `about-patterns.md` — 3-line hook rule (only 3 lines show before "see more"),
  skimmability, arrows/numbers/whitespace, three variants, red-flag handling.
- `experience-patterns.md` — results not responsibilities; leave `[bracketed]` gaps for you
  to fill rather than inventing numbers.
- `edge-pass.md` — strengths → the weakness a recruiter sees first → flip it → test for
  conversion → rewrite the whole profile around that one edge.

**2.3 Ship the profile.** Tagline, banner line, About, Experience, and the three-tier skills
strategy: top skills in About; a *short* list per experience entry (the transcript is blunt
that 40 skills under one job "looks really bad"); and the main Skills section **maxed out**,
because that's the section recruiters boolean-search and nobody reads.

Also: clean custom URL, and Featured populated with a case study that shows your *thinking*
(link the app inside the write-up rather than shipping a bare app link).

**Deliverable:** rewritten profile live; `corpus/profile/versions/` has v1; keyword brief archived.

---

### Phase 3 — Intel pipeline (week 2)

**3.0 Connect LinkedIn via Apify MCP. This is the whole connection step.** Register the Apify
MCP server in `.claude/settings.json` with your API token, and you are connected — Claude can
now discover and run LinkedIn scraper actors directly. Work conversationally:

```
you › search the Apify store for LinkedIn post scrapers. For the top 3,
      show me input schema, output fields, per-result pricing, and whether
      they need my session cookie.

you › run the best one against a single creator, 20 posts. Show me the
      raw JSON so I can see what normalize.py has to handle.
```

**For weeks 1–4, stop here.** MCP alone covers pulling your watchlist, grabbing a creator's
recent posts, and one-off research mid-draft. You do not need `scrape.py` to get value, and
writing it before you know which actor and which creators matter is premature.

Two things to confirm while you are in here: **per-result pricing** before you point anything
at 40 accounts, and that the actor uses its own proxies rather than **wanting your session
cookie** — never hand over your own session.

**3.1 `scrape.py` — a thin convenience wrapper, not an ETL system.** Once you know the actor
and the watchlist, a ~40-line script that loops the watchlist, calls the actor via REST, and
writes `intel/posts/{date}-{actor}.json` saves you from re-driving it conversationally each
time. That is all it is. No checkpointing, no incremental sync, no database writes — at ~$2
a refresh, re-pulling is cheaper than the code to avoid it. Keep the MCP server registered
regardless; ad-hoc pulls stay useful forever. Inputs: a watchlist of
20–40 creators in your pillars, plus keyword searches. Checkpoint by post id so re-runs are
incremental. Never use your own session cookie — the point of the proxy actor is that the
scrape isn't attached to your account.

**3.2 `normalize.py`.** Raw JSON → `posts` table. Compute `hook` (first 3 lines), engagement,
download images to `intel/images/`.

**3.3 `xfactor.py`.** Author baselines + per-post x-factor per §3.2. Materialize as a view so
it recomputes when new posts land.

**3.4 `intel/reports/top-posts.md`.** Top posts by x-factor with hook, link, image thumbnail
path. This is the file you actually read each morning.

**Deliverable:** `SELECT * FROM posts WHERE x_factor > 3 ORDER BY x_factor DESC` returns a
usable idea queue.

---

### Phase 4 — Retrieval + MCP (week 3)

**4.1 `embed.py` — two indices.**
- *Market index:* `voyage-3` over post text; `voyage-multimodal-3` over images.
- *Story index:* `voyage-3` over `title + tension + turn + result` per story file.

**4.2 `cluster.py`.** Agglomerative clustering on text embeddings → `template_id`
(recurring post skeletons). Same on image embeddings → `image_family_id`. The transcript's
"group by image" finding — that the *same visual concept goes viral repeatedly, across
different creators* — falls straight out of this, and a family with several high-x-factor
members is a format you can safely reuse.

**4.3 Why RAG here rather than just reading files.** Three concrete reasons:
- **Context economy.** A mature story bank is hundreds of entries. Loading it wholesale each
  session burns context and dilutes attention. Retrieval hands the writer 3–5 relevant,
  verified stories.
- **Grounding.** Retrieval + truth-table becomes an allowlist: if a claim isn't in what came
  back, the skill can't write it. That's the technical implementation of "which of these can
  you truthfully claim?"
- **Cross-modal recall.** "Find me posts whose *image concept* matches this idea" is only
  expressible over multimodal embeddings.

*Honest scoping note:* below ~100 stories, hybrid metadata filtering (`pillars`, `stage`,
`has_metric`) does most of the work and pure vector search adds little. Build the frontmatter
filter first; turn on vector search when the bank outgrows it. Don't add a vector database —
brute-force cosine over a few thousand vectors is sub-50ms.

**4.4 `mcp/server.py`.** FastMCP, registered in `.claude/settings.json`:

| Tool | Signature | Purpose |
|---|---|---|
| `search_stories` | `(query, pillar?, stage?, must_have_metric?, k=5)` | Ground authority posts |
| `get_truth_table` | `()` | The claim allowlist |
| `find_viral_posts` | `(topic?, min_xfactor=2.0, min_likes=750, since?, k=20)` | Idea + template sourcing |
| `get_template` | `(template_id)` | Cluster exemplars + extracted skeleton |
| `similar_images` | `(query_text_or_path, threshold=0.75)` | Image-concept research |
| `author_baseline` | `(handle)` | Sanity-check a creator before copying them |
| `my_performance` | `(window=30)` | Your own x-factor over time |
| `log_story` | `(text, pillars, metrics)` | Write path: "add this to my story bank" from anywhere |

**Why MCP earns its place — one leg weaker than it was.** Originally I justified this two
ways: portability, and a typed contract for scheduled cloud agents. **Cutting Phase 7 removed
the second reason entirely.** What remains is genuine but smaller: (a) the same corpus reachable
from Claude Desktop or mobile, so you can log a story or pull a template from your phone after
a meeting, and (b) typed tools instead of the model grepping JSON, which matters most for
`similar_images` and `search_stories` where the query is a vector operation rather than a
string match.

If you decide you only ever work in this repo, on this laptop, **the MCP server is skippable** —
the skills can read `intel/posts/*.json` and `corpus/stories/*.md` directly. Worth knowing
before Phase 4, since it is a day of work you can decline.

**Deliverable:** ask Claude "find me a proven template for a post about API pricing and pull
the story that fits it" and get a grounded answer in one turn.

---

### Phase 5 — Writing skills (week 3–4)

**5.1 `post-templatizer`.** Input: a high-x-factor post. Output: a skeleton separating
**static reusable scaffolding** from **variable slots** — the transcript's exact framing when
it prompts *"can you templatize it for me?"* — plus a note on which connective phrases carry
over verbatim. Store to `intel/reports/template-library.md` keyed by `template_id`.

**5.2 `authority-post`.** The workhorse. Pipeline:
```
pick pillar → find_viral_posts(pillar, min_xfactor)
  → choose template → search_stories(topic) → draft against the 6-part structure
  → self-check against truth-table → emit to drafts/queue/ with 5 hook variants
```
Structure enforced: **hook** (2–3 lines) → **bridge** (story) → **meat** (the educational
payload; go deeper than the source template did) → **mic drop** (two contrast lines: what we
overinvest in / what we neglect) → **engagement question or CTA**.
Voice constraint: first person, "how I did it," never "how to."

**5.3 `reach-post`.** Same machinery, `how-to` framing, broader topic.

**Every draft passes `voice-check` (Phase 1.5) before it lands in `drafts/queue/`.** The
writer skills do not emit directly; they emit into the gate, revise against the named tell,
and only then write the file. A draft that cannot pass in 3 loops is written out anyway,
flagged, and the failure is logged — persistent failures on the same feature usually mean
`voice.md` has a rule that is wrong, not that the writer is broken.

**5.4 `hook-lab`.** Given a finished body, generate 10 hooks and rank them against the hooks
of high-x-factor posts in the same cluster. Worth its own skill because the transcript
singles out hooks as where the human time actually goes.

**5.5 `image-brief`.** Output a paste-ready image prompt, structured the way the transcript
dictates one: reference the visual family, name the left/right or before/after contrast,
and — the key move — **describe the *feeling*, not the facts** (the fast train on the
crumbling bridge vs. the slow train on the solid one). The brief should end with the mic drop
it needs to reinforce.

**5.6 `story-bank-curator`.** Run at session end: diff the transcript for stories not yet in
the bank, propose new files, flag unverified numbers.

**Cadence this feeds (per transcript, job-seeker setting):** 3 posts/week — **2 authority,
1 reach**. Authority dominates because a hiring manager who lands on your profile scrolls to
your Activity, and what they need to see there is how you think, not something that went viral.

---

### Phase 6 — Targeting + outreach (week 4)

**6.1 `target-mapper` — guided manual by default.** LinkedIn people-search sits behind auth,
so this step is *not* hands-off unless you add a people-search scraper, which is a
meaningfully larger ToS and detection surface than pulling public posts. Two paths:

- **Guided (recommended, and what the transcript's speaker actually does — her People-page
  demo is her clicking live).** The skill reads the JD, extracts the team name, and hands you
  the exact filter sequence: company page → People → filter location → filter "product
  management" → drop location, add the team keyword (LinkedIn allows only one). You do ~4
  minutes of clicking and paste the names back. Claude does the profile triage and writes the
  company file. **Total human cost: about 4 minutes per company.**
- **Scraped.** An Apify people-search actor. Faster, materially more exposure.

Either way the output is `corpus/targets/companies/{company}.md` with two tiers: **peers**
(likely report to your HM) and **probable HMs**. The peer tier matters because peers are
easier to reach and sit one hop from the decision-maker.

**6.2 `comment-drafter`.** For each target, pull recent activity. Rules encoded:
- Skip announcement posts — you cannot add value to "I started a new position."
- Prefer posts where they shared a lesson.
- If their last post is stale, mine **their comments on other people's posts** instead, and
  answer the open question they left there better than anyone else did.
- Format: first name only, substantive value, end on an open-ended question.
- Output to `ops/engagement-queue.md` for approval. **Never auto-post.**

The mechanism being exploited is worth stating in the skill file so drafts stay on-target:
non-creators get few notifications, so your comment gets *seen*, and what they see next to it
is your name and **tagline** — which is why Phase 2 ships before Phase 6.

**6.3 Outreach scripts** in `ops/outreach-log.md`, with the transcript's hard sequencing rule:
**apply to the job first**, then comment, then connect. The four scripts (direct 15-minute ask;
ego appeal; the cheeky "you already eat three meals a day, spend one with me"; and the
"point me to the right person" redirect) go in the skill as templates to personalize —
they are starting points, not sends.

---

### Phase 7 — CUT

Removed at your direction, and correctly: **every single thing in the transcript is
interactive.** She types, reads, judges, and re-prompts. There is no cron, no nightly job, no
generated content calendar anywhere in the source. I invented that layer and it added most of
the plan's engineering weight for none of its value.

The system is driven by you, in a session, when you want a post.

**Self-performance is not a separate feature — it is `is_mine: true`.** See §3.3. It needs no
skill, no manual entry, and no scheduling: your own profile is just another `targetUrl` on the
same pull.

> Still open: `voice-diff` (compare a generated draft to what you actually published, to grow
> `voice.md`) would be an **on-demand skill you invoke**, never a scheduled job. Not in the
> transcript, not added unilaterally — say if you want it.

---

## 5. What you need to provide

### 5.1 Credentials and accounts
| Item | Needed for | Notes |
|---|---|---|
| **Apify API token** | Phase 3 | ~$1.50–2 per 1,000 posts on the actor researched. A 40-creator refresh is ~$2. Realistically **under $10/mo** unless you refresh constantly |
| **Voyage AI API key** | Phase 4 | Text + multimodal embeddings; generous free tier |
| **LinkedIn Premium** (optional) | Phase 6 | Transcript recommends it *only while actively searching* — InMail + open profile + top-applicant signals; ~$100/mo |
| Image generation access | Phase 5 | ChatGPT or equivalent; the repo produces the brief, not the pixels |

### 5.2 Content inputs — the ones only you can supply
1. **Your full current LinkedIn profile text** — every section verbatim (headline, about,
   each experience entry, skills, education). Paste into `corpus/profile/current.md`.
2. **Your resume** (most recent, ideally the long version).
3. **5 target job descriptions**, same role family. This is a real decision, not a formality —
   the miner will halt if they're scattered, and that halt is the system working.
4. **Your verified metrics** — for the truth table. Numbers you delivered, with what would
   substantiate each. Ranges and honest estimates are fine; label them.
5. **15–25 career stories** — you don't write these, you answer the interview. But block the
   time; this is the one input with no shortcut.
6. **A creator watchlist**: 20–40 LinkedIn accounts in your pillars whose posts are worth
   learning from. Mix people your size with 2–3 large accounts.
7. **Your LinkedIn data export** — Settings → Data Privacy → Get a copy of your data.
   Fully sanctioned, arrives in minutes to a day, ships as CSVs. Gives you your own posts and
   comments for `is_mine` baselining, and your **messages**, which are strong voice samples.
   Check what your export actually contains when it lands — the file set has changed over the
   years, and post *analytics* coverage in particular is thin depending on account type.
   For self-metrics, pasting your own numbers at T+24h/T+72h takes ~30s per post and removes
   any need to scrape yourself.
8. **Writing samples for voice capture (see Phase 1.5)** — this is a bigger ask than it
   looks and it is worth taking seriously:
   - **~5,000 words minimum** of your real writing. Best sources: Slack/Discord messages,
     transcribed voice notes, long emails, PRDs and post-mortems. LinkedIn posts last.
   - **3–5 pieces you are genuinely happy with**, marked as exemplars.
   - **A negative set** — writing that sounds nothing like you, and any AI draft you
     rejected, annotated with why.
   - **A 15-minute voice interview, dictated rather than typed.** I ask, you talk, we
     transcribe. Captures your spoken rhythm and doubles as story-bank raw material.
   - **Shortcut:** your **Google Drive MCP is already connected** — I can search your Drive
     for PRDs, post-mortems, and strategy docs and pull voice samples straight out, no manual
     gathering. Authorizing the **Gmail** connector adds long-form emails, which are among the
     best sources available. That is likely faster than digging through Slack exports.

### 5.3 Decisions I need from you before Phase 2
- **Target role + niche**, in the four-axis form: domain, product type, superpower, company stage.
- **Are you actively job searching, or building presence?** Changes the authority/reach ratio
  and how hard the profile repoints.
- **Posting days and realistic weekly time budget.**
- **Virality threshold** — the transcript uses 750+ likes; adjust to your niche's scale.
- **Are you posting while employed?** Determines how the pillars are chosen (the
  "looks good to both current and future employer" test).

### 5.4 Ongoing (small, but the system dies without it)
- 10 minutes at session end to approve story-bank additions.
- Human edit pass on every draft, especially hooks — non-negotiable per the transcript.
- Approve the engagement queue before anything gets posted.

---

## 6. Risks and constraints

- **LinkedIn scraping violates LinkedIn's Terms of Service**, regardless of proxying. The
  proxy-actor approach in the transcript keeps the activity off your own account, which is why
  it's the recommended pattern, but the risk isn't zero and it's yours to accept. Keep to
  public posts, keep volume modest, don't redistribute scraped data. If you'd rather avoid it:
  Phases 1, 2, 5, and 6 all work without the intel layer — you lose x-factor ranking and
  template mining, and you'd source templates manually instead. That's a smaller loss than it
  sounds like in month one.
- **Don't over-build the retrieval layer early.** With 20 stories, frontmatter filtering is
  enough. Phase 4 pays off at scale, not on day one — ship Phases 1–2 first and resist
  reordering.
- **Automation without the human gate produces generic content.** The transcript is explicit
  that AI output is a first draft and the hook is where the real work happens. Every agent in
  the system is interactive by design.
- **Cost control:** cache embeddings by content hash so re-pulls don't re-embed unchanged
  posts. Scraping itself is cheap enough (~$2/refresh) that it needs no optimization.
- **Attribution:** when you reuse someone's visual concept or a detailed infographic, credit
  them; the transcript's own rule is credit-by-default, ask-when-in-doubt, and never
  word-for-word without a pre-agreed swap. Written structural templates don't need credit.

---

## 7. Suggested first week

| Day | Do |
|---|---|
| 1 | Phase 0 skeleton + `CLAUDE.md`. Gather the 5 JDs and paste your current profile |
| 2 | Story-bank interview (90 min, dictated). Truth table. Dump writing samples into `corpus/identity/voice/samples/` |
| 3 | ICP doc + pillars. Write `jd-keyword-miner`, run it, check the coverage gate |
| 4 | Write `profile-rewriter` + reference files. Generate the rewrite |
| 5 | Human edit pass. **Ship the new profile.** Snapshot to `versions/` |
| 6 | **Register Apify MCP — this is your LinkedIn connection.** Find a LinkedIn scraper actor, check pricing, pull one creator's posts. Assemble the watchlist |
| 7 | Build the voice fingerprint from your samples. Write one authority post by hand using the 6-part structure, off one story. Publish it — and keep the generated draft, it is edit-diff sample #1 |

Ship the profile before you optimize the content engine. Every post you write from here sends
traffic to it, and right now that traffic converts against an unoptimized page.
