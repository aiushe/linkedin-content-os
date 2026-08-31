# LinkedIn Content OS

**A human-gated collaborative system for grounded LinkedIn drafting**

| Field | Value |
| --- | --- |
| Week 3 project | Bring-your-own use case (closest to 3D: GTM Ideation to Copy) |
| Build track | Track 2 — LangChain + LangGraph (Python) |
| Repository | https://github.com/aiushe/linkedin-content-os |
| Video demo | [PASTE LINK] |
| Model provider | Nebius Token Factory |

---

## 1. Project overview

Most AI writing tools fail in one of two ways: they invent numbers that sound plausible, or
they flatten the author into generic LinkedIn voice. This project treats both as engineering
problems with deterministic answers rather than prompt-tuning problems.

The agent turns a rough post idea into a LinkedIn draft, retrieving from my own story bank and
a market-intelligence corpus. Before the draft reaches me it passes through three deterministic
checks — claims, voice, confidential terms — that run in pure Python at zero model cost. Those
checks **report**; they do not decide. Every draft reaches me with a complete observation
snapshot of what could be grounded and what could not, and I choose what happens next.

Nothing publishes. Nothing is saved to the queue without my explicit approval.

### The one-liner

My agent helps me, a PM targeting agentic-product roles, turn a rough post idea into a LinkedIn
draft that is measurably close to my voice and whose every factual claim is labelled grounded or
ungrounded, in a local Streamlit app, replacing the 45–90 minutes of drafting plus
self-fact-checking each post costs today. It does retrieval, drafting and computed critique on
its own using 11 read tools, hands the draft plus its full observation report to me before any
write, and I know it works when every planted claim in an adversarial evaluation set is detected
and surfaced, and every case still delivers a draft I can act on.

### A design reversal worth stating up front

This project began with fail-closed gates and automatic revision paths: an unmatched claim
blocked the draft, an unready voice fingerprint returned `INDETERMINATE`, and the graph escalated
rather than deliver. After first real use that proved counterproductive. **A tool that blocks
constantly gets deleted.** The detection work is still the most valuable part of the system, but
its output is now an observation for the writer rather than a veto over them.

Section 11 treats this as the central learning rather than an implementation detail.

---

## 2. Agent framework

| Field | Answer |
| --- | --- |
| Agent goal | Turn a rough content idea into a grounded, voice-aware LinkedIn draft, delivered to a human with a complete report of what it could and could not ground. |
| Surface | Local Streamlit studio (`app.py`); the same read tools are also exposed over MCP to Claude Code. |
| Steps, in order | 1. Recall approved profile memory  2. Classify intent (advisory)  3. Retrieve stories, claim allowlist, market brief  4. Draft body plus hooks  5. Run the three deterministic checks  6. Compute a critique from those findings  7. Deliver to the human via `interrupt()`  8. Save to `drafts/queue/` only on approval |
| Tools | `search_stories`, `get_allowlist`, `get_truth_table`, `check_claims`, `get_voice_report`, `find_viral_posts`, `get_template`, `author_baseline`, `my_performance`, `similar_images`, `web_search` — all READ. |
| Writes | Two, both human-initiated: the queue save on `approve`, and a truth-table row on `source`, which appends only the exact claim, proof, date and verification text the user typed. |
| Memory | Session: `thread_id` plus `MemorySaver` checkpointer. Semantic long-term: the local private corpus. Episodic: story `used_in` back-references. Personal: a narrow Mem0 Platform adapter holding only user-approved profile facts. |
| Never do | Publish or post anywhere. Send a message. Auto-repair or silently drop a detected claim. Write outside `drafts/queue/` and the user-entered truth-table row. Ingest the private corpus into an external service. |
| Human in the loop | `interrupt()` before every write. Seven actions: `approve`, `edit`, `feedback`, `source`, `reject`, `retry`, `annotate`. |
| When it breaks | Five-class taxonomy: TRANSIENT retries twice with backoff; DEGRADABLE proceeds with a recorded reason; CAPABILITY, INTEGRITY and LOOP are recorded in state and surfaced in the report. No class blocks delivery. |
| Success measure | Every case delivers a draft to the human with an intact observation snapshot, and every planted claim in the adversarial set is detected and shown. |

### Router intents

Six classes, not four: `authority`, `reach`, `comment`, `profile_rewrite`, `outreach`,
`out_of_scope` (`agent/state.py`). The 0.70 confidence floor still exists in config and is
recorded on the state, but it no longer gates anything — the router now supplies a *suggested*
format, and every request reaches drafting.

---

## 3. Architecture

Nine graph nodes over a shared state object, with a memory checkpointer for resumable
human-in-the-loop runs.

```
START -> profile_memory -> intake_router -> ground -> write -> gate -> critique -> hitl
  hitl -> approve   -> commit -> drafts/queue/
  hitl -> edit      -> gate      (re-observe the human's own text)
  hitl -> source    -> gate      (re-observe against the widened allowlist)
  hitl -> feedback  -> write     (user direction, highest-priority writer input)
  hitl -> retry     -> write
  hitl -> annotate  -> hitl      (attach a note, stay on the review surface)
  hitl -> reject    -> END
```

Every transition out of `write`, `gate` and `critique` is unconditional. There is no `fallback`
node, no `escalate` node, and no automatic revision loop: revision happens only because a human
asked for it.

| Node | Model | Role |
| --- | --- | --- |
| `profile_memory` | none | Reads user-approved Mem0 profile facts. Explicitly non-evidentiary; degrades to a context note when unavailable. |
| `intake_router` | Qwen3-30B-A3B | Structured classification into one of six intents. Advisory; selects the skill playbook and the market-intel budget. |
| `ground` | Qwen3-30B-A3B | ReAct retrieval loop over the 11 read tools; bounded by `recursion_limit` 12. |
| `write` | Qwen3.5-397B-A17B | The only node producing prose. Receives stories, allowlist, market brief, the authored skill playbook, and all prior user directions. |
| `gate` | none | Pure Python. Claims, voice and confidential terms. Runs in single-digit milliseconds and costs $0. |
| `critique` | Qwen3-30B-A3B | Reflection against a COMPUTED report, not an opinion. Falls back to a fully deterministic critique when models are unavailable. |
| `hitl` | none | `interrupt()` with the draft, all three reports, evidence, degradation reasons and running cost. |
| `commit` | none | Writes the draft plus its full observation snapshot to `drafts/queue/`. |

`agent/nodes/profile_rewrite.py` and `agent/nodes/outreach.py` exist and the router classifies
into their intents, but neither node is wired into `build_graph` yet. See section 12.

### Authored skills are injected, not just loadable

The eleven `SKILL.md` files under `.claude/skills/` are the playbook, mapped to graph intents by
a seven-role table in `agent/skills.py`. `role_block()` is called by both `write` and `critique`,
so editing a `SKILL.md` changes agent behaviour. Front matter is always cheap and available; a
skill body is pulled into context only when its role is selected. Skills are instructions and
never evidence — nothing loaded there can widen the factual allowlist.

---

## 4. The three deterministic checks

This is the part of the system I would defend hardest. All three are pure Python, cost nothing,
and run on every draft. All three **report**; none of them blocks.

### Claim check (`pipeline/claims.py`)

Extracts every number, superlative and attribution from a draft and matches it against an
allowlist assembled from two sources: verified rows in the truth table, and story metrics
explicitly marked verified. Matching is deliberately conservative — a near-match is an unmatched
claim, not a pass. Each finding carries its span, kind, containing sentence and line number, so
the report is actionable rather than a bare count. Every detected claim survives into the report
intact; nothing is silently dropped or auto-repaired.

When the allowlist is empty, every claim is reported as ungrounded. That is the honest reading:
an unseeded corpus cannot ground anything.

### Voice check (`agent/gates.py` over `pipeline/voice.py`)

Scores 15 numeric stylometric features against a fingerprint computed from real writing samples:
sentence-length median and standard deviation, paragraph count and length statistics, contraction
rate, em-dash rate, colon and semicolon rate, parenthetical rate, hedge rate, first-person rate,
list-line rate, type-token ratio and mean word length, plus a non-scored opening-move label.

Two features (`paragraph_length_mean`, `paragraph_length_stdev`) are excluded for `short_post`
targets, because a three-line LinkedIn post cannot meaningfully be compared to long-form
paragraph statistics — that exclusion was a source of false flags. Thirteen features are
therefore scored for a short post, and the report names exactly which.

Below 3 samples or 1,500 words the verdict is `warn` with an explicit reason ("Voice fingerprint
is not ready"), so an unready fingerprint reads as unmeasured rather than as approval.

### Confidential-terms check (`pipeline/confidential.py`)

Matches a private, optional, human-maintained term list against the draft and reports matched
terms with their line numbers. Advisory by design: the Git boundary, not this check, is what
keeps local drafts out of the public repository.

### The reduction

`reduce_verdicts` summarizes the three into one of `pass`, `warn`, `revise` — a readability
convenience for the review surface. Its docstring states the constraint directly: summarize
without letting any finding block a draft.

### The bug that shaped all of this

The original voice scorer failed **open**: with an empty fingerprint the feature loop ran zero
iterations, so every draft "passed" a check that was examining nothing. That is the worst
possible failure for a system whose purpose is showing you what it could not verify — a green
light that means nothing. The fix was never "block harder"; it was to make an unmeasurable input
report itself as unmeasured. Every check now distinguishes *clean*, *flagged*, and *could not
tell*.

---

## 5. Market intelligence: two tiers

Market data decides shape, length and angle. It never touches facts or phrasing.

| | Scored (batch) | Unscored (live) |
| --- | --- | --- |
| Source | `harvestapi/linkedin-profile-posts` via REST | `harvestapi/linkedin-post-search` via Apify MCP |
| Cadence | Offline, periodic | Runtime, cached 12 hours |
| x-factor | Yes: self-excluded 30-day per-author baseline | Structurally impossible |
| Answers | What reliably outperforms for people like me | What is happening this week |

The distinction is not stylistic. `xfactor.py` requires at least 10 posts from the same author to
compute a baseline. A keyword search returns roughly 25 posts from 25 different authors, so every
`x_factor` is necessarily null. Ranking those by raw likes is exactly the signal x-factor exists
to replace, so live results are hard-coded `scored=false` and can never justify a claim.

### Cost controls

- Intent gate: only `authority` and `reach` may spend; `comment` never fetches.
- One fetch per run; never re-fetched during revision.
- Disk cache with a 12-hour TTL, so demo takes and eval reruns are free.
- Deterministic compression: top-5 hooks truncated to 200 characters reach a model context, never
  full post bodies (~400 tokens instead of ~7,000).
- Hard caps on posts per call (`INTEL_MAX_POSTS=25`), a 25-second timeout, and per-call USD
  accounting.

---

## 6. Datasets used

| Dataset | Size | Role |
| --- | --- | --- |
| Story bank (`private/stories/`) | 9 stories | Grounded narrative evidence; frontmatter carries verified metrics |
| Truth table | 8 verified rows | The factual allowlist. Only these values match as grounded |
| Voice samples | 7 files, 2,658 words | Source of the 15-feature stylometric fingerprint |
| Target job descriptions | 5 JDs | Input to the keyword-coverage brief |
| Creator watchlist | 12 authors, 225 posts | Batch market pull; x-factor coverage 125/225 |
| Fixture corpus (tracked) | synthetic | Ships with the repo so graders can run the suite without my private data |

Counts above are the live output of `scripts/audit.py`. The entire private corpus is gitignored,
as are all drafts and rebuildable market data. The repository ships a clearly-labelled synthetic
fixture corpus so the eval suite runs for anyone who clones it.

---

## 7. Models and cost

| Role | Model | Rate per 1M |
| --- | --- | --- |
| Router | `Qwen/Qwen3-30B-A3B-Instruct-2507` | $0.10 in / $0.30 out |
| Critic | `Qwen/Qwen3-30B-A3B-Instruct-2507` | $0.10 in / $0.30 out |
| Writer | `Qwen/Qwen3.5-397B-A17B` | see Nebius list price |
| Embeddings | `Qwen/Qwen3-Embedding-8B` | — |

The deterministic checks cost nothing, because they run no model at all. That per-node split is
the evidence for the minimal-intelligence argument rather than an assertion of it: the most
safety-relevant component in the system is also the cheapest.

**Measurement note.** The per-node costs recorded during the earlier live run
(`intake_router $0.00006`, `ground $0.00155`, `write $0.00180`, `market_brief $0.00088`,
`market_search $0.01500`) were taken with `meta-llama/Llama-3.3-70B-Instruct` as the writer and
before the advisory reduction. The writer has since changed and those figures need a re-run
before they are quoted as current.

An earlier configuration used Qwen3-32B for the router. The capability probe showed it emitting
visible chain-of-thought, and thinking tokens bill as output at three times the input rate, so a
"cheap" classifier was quietly expensive. Swapping to the non-thinking instruct variant fixed it
at identical list price.

---

## 8. Evaluation

Eleven cases in `evals/golden.jsonl`: six clean, four adversarial poisons designed to bait a
fabricated claim, and one explicitly labelled known limitation. The suite runs deterministically
offline against the fixture corpus, and live against real models.

A case passes only when it is **delivered** — a draft was produced and reached the human — *and*
its content expectation holds. Delivery is part of the pass condition, because a system that
protects the user by refusing to produce anything has failed at its job.

| Metric | Offline (fixtures) |
| --- | --- |
| Planted-claim recall | 4/4 (100%) |
| Claim precision on clean drafts | 100% (0 false flags) |
| Clean drafts left unflagged | 6/6 |
| Drafts produced and delivered | 11/11 |
| Mean user-requested revisions before review | 0.00 |
| p50 latency | 0.0041s |
| p95 latency | 0.0365s |

The clean set deliberately includes four hyphenated-compound cases (`first-class`, `first-mover`,
`only-child` and one retrieval case), because those are where a superlative detector most easily
produces false positives. Precision on them is the reason the claim check can stay conservative
without becoming noisy.

**Live results need a re-run.** The last live measurement (p50 141.5s, 5/5 clean) predates both
the writer swap and the advisory reduction, and its metric definition has since changed. It is
recorded here as history, not as a current number.

### The most important finding: the first live run proved the evaluation wrong, not the system

The live run reported a fabrication catch rate of 1/5 and looked like a catastrophic regression.
It was not. Three poison cases returned pass with zero unmatched spans, meaning the draft
contained no ungroundable claim at all. Given the allowlist in its prompt, the live writer simply
refused to fabricate. There was nothing left to catch.

The metric had encoded "the check must flag this", which is only true when the writer produces
the fabrication in the first place. That held for the canned offline draft and not for a real
model. Two different successes were being conflated, and one of them was scored as failure:

- **Prevention:** the writer never emitted the claim (3 cases)
- **Defense:** the writer emitted it and the check flagged it (1 case, span `"first"`)
- **Failure:** the writer emitted it and the check missed it (0 cases)

Only the third is a real failure, and it did not occur. The correct measure is whether an
ungrounded claim reaches the human *unlabelled* — and it never did. This is the concrete version
of the lesson that evals must be designed before you trust their numbers.

### Known limitations are encoded, not just noted

`poison-laundering` plants the hedged quantity "roughly half", which carries no digit and which
the regex extractor cannot reach. Rather than let it quietly depress recall, it carries
`kind: known_limitation` in the golden set, is excluded from measured recall with a written
reason, and reports as `KNOWN LIMITATION` in `evals/results.md`. A known gap should be visible in
the output, not averaged into a number.

---

## 9. Iterations and what broke

The debugging path was more instructive than the build. Every item below was found by running the
system, not by reading it.

| Symptom | Root cause | Fix |
| --- | --- | --- |
| Every draft passed the voice check | Empty fingerprint meant the feature loop ran zero iterations and failed OPEN | Explicit not-ready verdict with a reason; unmeasurable inputs report as unmeasured |
| Demo produced plausible output with no model calls | Nothing loaded `.env`, so the agent silently ran offline with canned drafts | `load_dotenv()` in `agent/config.py` |
| Every eval case escalated, no reason recorded | OpenAI account had no active billing (429 `billing_not_active`); the router swallowed the exception into a string | Record errors in state; switch provider to Nebius |
| Same failure again in the pipeline CLIs | Only the agent loaded `.env`; standalone scripts did not | `load_dotenv()` in `pipeline/common.py`, imported by every CLI |
| Run hung for 10+ minutes at 1.6s CPU | Unbounded Apify MCP fetch; a hang raises nothing, so `except` never fires | `asyncio.wait_for` 25s; `recursion_limit` on the ReAct loop |
| Apify returned 404 | REST routes on `user~actor`, not the store's `user/actor` form | Convert the separator automatically |
| API token printed in a traceback | Token passed as a URL query param, which `raise_for_status` echoes | Authorization header; token rotated |
| Live catch rate read 1/5 | The metric assumed the writer always emits the poison | Score on whether an ungrounded claim reaches the human unlabelled |
| Short posts flagged on paragraph statistics | Long-form paragraph features compared against three-line posts | Exclude two paragraph features for the `short_post` target and name the exclusion in the report |
| The tool was accurate and unusable | Fail-closed gates blocked ordinary drafts; escalation paths produced nothing to work with | Reduce all three checks to advisory; remove `fallback`, `escalate` and the automatic revision loop |

---

## 10. Prompts used during development

Selected prompts that shaped the build, rather than a transcript.

**Architecture, before any code**

> Give me an EXTREMELY detailed plan of what needs to be implemented. Ask me questions about
> things that are unclear and explain what will change and what the effort is.

Planning before implementation surfaced the fail-open voice scorer and the three-table
truth-file parsing problem while they were still cheap to fix.

**Cost discipline**

> How will you write search_trending_posts so that it is not wasting cost or tokens?

This produced the six-control design: intent gate, once-per-run, TTL cache, deterministic
compression, fixed arguments, and USD accounting. The token leak was roughly fifty times larger
than the dollar leak, and would not have been found by asking about cost alone.

**Refusing to accept descoping**

> What else did you cut?

An audit against the repository showed the design was using a fraction of the pipeline modules,
MCP tools, authored skills and product pillars that had been built. Several capabilities had been
dropped without ever being raised as a decision. The skills injection in section 3 is a direct
result: they were loadable but unused until this audit made that visible.

**Never guess a configuration value**

> What are other companies aside from Voyage I can use?

Led to querying the endpoint for its real model list rather than trusting documentation, and then
to a capability probe that tests structured output and tool calling per model instead of assuming
support.

---

## 11. Learnings

**A check that blocks is a check that overrides the user**

This is the reversal at the centre of the project. The first design was fail-closed on principle:
unmatched claim, no draft. It was defensible in a design document and unusable in practice,
because ordinary honest drafts trip conservative detectors constantly, and a tool that says no
more often than yes gets deleted. What actually produces good posts is detection plus a complete,
legible report handed to a person who can judge. The detector did not get weaker — every claim,
voice difference and confidential match still survives into the report intact. It stopped being
the decision-maker.

**"Could not tell" is a third state, and omitting it is a bug**

The fail-open voice scorer approved everything precisely because it collapsed *unmeasurable* into
*clean*. Blocking was one way to fix that, and it turned out to be the wrong one; the necessary
fix was making the third state visible. An unready fingerprint now says so in words, on the
review surface, in the saved frontmatter.

**A hang is not a slow error**

The error taxonomy handled failures that raise. A call that never returns raises nothing, so no
handler fires and the graph waits forever. Unbounded network calls and unbounded loops need
limits, not handlers.

**Configuration bugs are about location, not value**

Two separate outages had the same shape: a credential that existed but was not loaded where it
was read, and a token passed correctly but through a field that gets logged. Neither was caught
by tests, because tests check what a value equals and not where it travels.

**Deterministic rubrics beat model judgement where they apply**

The critic reads computed output — flagged features and an unmatched-claim list — instead of
judging quality freely, and falls back to a fully deterministic critique when models are
unavailable. That makes the reflection loop cheap enough for a small model and makes its output
reproducible.

**Prevention and defense are different successes**

Putting the allowlist in the writer prompt is prevention; the check is defense. The live run
showed prevention doing most of the work, which is the cheaper outcome, but the system still
needs the check because prevention is probabilistic and detection is not.

---

## 12. Known limitations

- Hedged quantities such as "roughly half" carry no digit, so the regex claim extractor cannot
  reach them. This is encoded as `poison-laundering` with `kind: known_limitation` and excluded
  from measured recall. A semantic extractor should be added as a second, advisory detector.
- The live latency figure (p50 141.5s) predates the current writer model and has not been
  re-measured. The likely contributors are the intel timeout, ReAct iterations and inference
  time; this has not yet been isolated.
- Clustering full post text groups by topic more than by structure, so `template_id` may not mean
  what its name suggests. Clustering on the structural features already computed for the voice
  fingerprint would be a better fit and needs no API.
- `agent/nodes/profile_rewrite.py` and `agent/nodes/outreach.py` are implemented and the router
  classifies into both intents, but neither node is wired into `build_graph`, so those requests
  currently fall through to the standard drafting path.
- The confidential-terms list is optional and human-maintained. An empty list produces a clean
  report, which is accurate but easy to misread as verified-safe.

---

## 13. What I would build next

- **Persist and diff the human edit.** The `edit` action already captures the revised text into
  state; the difference between the generated draft and the approved one is the highest-value
  signal the system produces, and it is not yet stored or analysed across runs.
- **Wire the profile-rewrite and outreach branches** into the graph, including the 0.75
  keyword-coverage brief, so the two intents the router already recognises have real nodes.
- **A semantic claim detector** running alongside the regex extractor, advisory only, so hedged
  quantities are surfaced without weakening the deterministic path.
- **Isolate and reduce live latency**, then re-measure cost per post-ready draft end to end on
  the current model configuration.

---

## Appendix: verification

```bash
uv sync --extra dev
uv run pytest -q                          # 128 passed
uv run ruff check . --exclude .venv
uv run python scripts/audit.py            # corpus and data-health counts
uv run python evals/run.py                # fixture suite
```

The fixture suite measures detector recall for planted ungrounded claims, precision on clean
drafts (including hyphenated compounds), and whether the user received a draft. It does not use
refusal, containment, or safety rates, because this system does not refuse.
