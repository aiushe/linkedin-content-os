# Week 4 — Evaluation Plan (LinkedIn Content OS)

Track 3: evaluate my own Week 3 agent with a private reviewer dataset.
Corpus decision: **private reviewer corpus**, with personal memory off and anonymized labels in
all public materials.
Execution decision: **full live runs**, baseline and post-improvement, on the same dataset version.

---

## 0. Read this first: five problems with the obvious plan

The obvious plan is "re-run `evals/run.py`, add LangSmith, report the numbers." That plan fails
the assignment. Here is why.

### 0.1 The current headline metric is saturated. There is no delta to measure.

Week 3 concluded — correctly — that the right metric is whether an ungrounded claim reaches the
human *unlabelled*. Measured result: 0 failures live, 4/4 recall and 100% precision offline,
11/11 delivery. Re-running that as a Week 4 baseline reports 100% and improves to 100%.

The project is graded on **measured delta**. Metrics that are already at ceiling produce none.
Week 4 needs metrics with documented headroom. Section 12 of the Week 3 doc already lists four:

- hedged quantities ("roughly half") are undetectable by the regex extractor — recall 0%
- p50 latency 141.5s, never isolated or reduced
- `profile_rewrite` and `outreach` nodes exist but are **not wired into `build_graph`**, so those
  two intents fall through to the drafting path — task completion on them is effectively 0%
- clustering groups by topic rather than structure, so `template_id` is misleading

Those four gaps are the Week 4 project. The failure analysis is half-written already.

### 0.2 The current eval suite is a unit test for `pipeline/claims.py`, not an agent eval.

`evals/run.py:main` sets `AGENT_OFFLINE=1` by default. p95 latency of 0.0365s means no model ran.
Six of eleven cases are hyphenated-compound false-positive checks against a single regex. That is
a good regression test for a detector; it is not evidence about an agent.

**Keep it** as the fast CI gate. Build a **separate live suite** for the graded work. Do not try
to make one runner serve both.

### 0.3 Nothing measures whether the draft is about the right story.

`ground` runs a ReAct loop over 11 read tools against 9 stories. No metric checks which story came
back. A voice-perfect, fully-grounded post about the wrong project is useless to the user — this
is a quality metric that maps directly to the user outcome and it is entirely missing.

It also has real headroom, which the claim metric does not.

### 0.4 `evals/run.py` will silently lose the traces you most want.

`run_live_case` calls `process.terminate()` on timeout. LangSmith flushes traces from a background
thread; SIGTERM discards whatever is queued. Every timed-out case — the most interesting failures
in the run — arrives in LangSmith as nothing at all. Fix before measuring, not after.

Also: `gate` is pure Python and will not appear in the trace tree at all. The most
safety-relevant component in the system would be invisible in the trace evidence submitted as
proof that it works.

### 0.5 Latency is the wrong headline cost metric for this agent.

The stated user outcome is replacing 45–90 minutes of drafting and self-fact-checking. Against 45
minutes, 141 seconds is noise. Optimising it is engineering vanity unless it is failing an SLA.

The cost metric that actually predicts value is **human minutes to a post-ready draft** — review
cycles times review time. `revision` is already on the state. Measure it on a 10-case
hand-reviewed subset and report it separately from the automated metrics. Keep p95 latency as a
guardrail metric ("did an improvement make this materially worse"), not as a headline.

---

## 1. The Primer (evaluation one-liner)

> I will measure claim-leak rate, story-retrieval accuracy, voice distance, intent task-completion
> and cost-per-delivered-draft on my LinkedIn Content OS drafting agent, using a golden dataset of
> 44 hand-labelled cases (22 happy-path, 13 edge, 7 known-failure, 2 adversarial) spanning all five
> router intents, with code-based evaluators for claims, voice, trajectory, latency and cost, and
> an LLM-as-judge for grounding faithfulness calibrated against 15 hand-labelled cases.
> Pass bar: zero unlabelled leaks, story-retrieval top-1 at or above 85%, mean voice |z| at or
> below 1.0, 100% intent completion, p95 latency at or below 90s, cost at or below $0.05 per
> delivered draft. Baseline vs post-improvement traced in LangSmith project `lco-eval`.

Quality bars are set a priori. **Latency and cost bars are set after a 5-case live pilot**, because
the writer model changed since the last measurement and any number quoted today is fiction.

---

## 2. The Framework

| Field | Answer |
| --- | --- |
| **Agent under test** | LinkedIn Content OS drafting agent (`agent/graph.py`), nine-node LangGraph: profile_memory to intake_router to ground to write to gate to critique to hitl to commit. |
| **User outcome** | A LinkedIn draft grounded in the user's real, verified experience, in the user's voice, with every factual claim visibly labelled grounded or ungrounded, so the user can approve it in minutes instead of writing and self-fact-checking for 45 to 90. |
| **Metrics** | (1) Claim leak rate, numeric and hedged classes. (2) Story-retrieval top-1 accuracy. (3) Voice distance, mean absolute z. (4) Intent task-completion, trajectory. (5) Cost per delivered draft plus p95 latency. |
| **Judge method** | 1: code, against hand-labelled per-case ground truth. 2: exact match on story id. 3: code, from `pipeline/voice`. 4: code, trajectory over the trace node path. 5: code, from LangSmith run metadata. Plus an LLM-as-judge for grounding faithfulness on a 15-case calibration subset. |
| **Golden dataset** | Private reviewer package, version `v1`: 44 cases from nine anonymized source records, queued-draft patterns, target-role materials, market-post patterns, and 11 migrated fixtures. All labels by hand. |
| **Pass bar** | 0 unlabelled leaks; story top-1 at or above 85%; mean voice \|z\| at or below 1.0; intent completion 100%; p95 at or below 90s; cost at or below $0.05 per delivered draft. |
| **Instrumentation** | One trace per case, run name `case:{id}`. Child runs for every node including a `@traceable`-wrapped `gate`. Metadata: case_id, kind, intent_expected, prompt_version, agent_sha, dataset_version, run_group, writer_model, router_model, offline flag. Tags: kind, intent, run_group. |
| **Baseline run** | `run_group=baseline`, offline suite for regression plus 44 live cases. Numbers, project link, one fully verified trace. |
| **Failure analysis** | Top 3 clusters by frequency, one linked trace per cluster, cost per cluster in human-rework minutes. |
| **Improvement hypotheses** | (1) Wire profile_rewrite and outreach into the graph. (2) Structure-based story retrieval. (3) Second advisory semantic claim detector for hedged quantities. (4) Parallelised grounding plus ReAct iteration cap. Predicted deltas pre-registered before running. |
| **Post-improvement run** | `run_group=improved`, identical dataset version and metadata schema, LangSmith comparison view. |
| **What is next** | Top remaining failure mode, next week's hypothesis, production monitoring thresholds. |

---

## 3. Metrics in detail

| # | Metric | Exact definition | Judge | Expected baseline | Bar |
| --- | --- | --- | --- | --- | --- |
| 1 | **Claim leak rate** | Ungrounded claims present in the final draft that do **not** appear in `claims_report.unresolved`, divided by total ungrounded claims present. Split into `numeric` and `hedged` classes. | Code + per-case hand label | numeric ~0% leak (saturated); **hedged 100% leak** | 0% numeric, at or below 30% hedged |
| 2 | **Story retrieval top-1** | `expected_story_ids[0]` equals `state["stories"][0]["id"]`. Report top-3 recall as secondary. | Exact match | unknown, estimate 60 to 75% | at or above 85% |
| 3 | **Voice distance** | Mean absolute z across `scored_features` versus the fingerprint. Continuous, not the pass/warn/revise verdict. | Code (`pipeline/voice`) | unknown | at or below 1.0 |
| 4 | **Intent task completion** | The trace node path matches the expected path for the labelled intent. `profile_rewrite` and `outreach` currently cannot pass. | Code, trajectory | approximately 60% (3 of 5 intents) | 100% |
| 5 | **Cost per delivered draft / p95 latency** | Summed token cost across child runs, divided by cases that both produced a draft and reached `hitl`. p95 from run durations. | Code, LangSmith metadata | re-measure; prior figures predate the writer swap | set after pilot |

**Metric 3 note.** `safe_voice_score` currently returns a verdict derived from
`VOICE_Z_THRESHOLD`. As an eval metric that is lossy and it moves whenever the threshold moves.
Use mean absolute z as the metric; keep the verdict as a display artifact only.

**Human-minutes side metric.** On a 10-case subset, review each draft by hand and record: number
of `feedback`/`retry` cycles before approval, and wall-clock review minutes. Report separately.
This is the metric that actually predicts user value; it is not automatable and that is fine.

---

## 4. Golden dataset — 44 cases

### 4.1 Distribution

| Type | Share | N | Contents |
| --- | --- | --- | --- |
| Happy path | 50% | 22 | Well-formed ideas across all five intents, each with a clearly correct source story. |
| Edge | 30% | 13 | Ambiguous intent, two plausible stories, partial data, an idea with no supporting story, out-of-scope requests, very short and very long inputs. |
| Known failure | 15% | 7 | Hedged quantities, profile_rewrite and outreach cases, topic-similar-but-wrong-story traps, the existing `poison-laundering` case. |
| Adversarial | 5% | 2 | Prompt injection in the idea text; an instruction to bypass the claim check. |

### 4.2 Sources, in order of preference

1. **Real** — 4 queued drafts and their originating ideas; 9 stories in `private/stories/`, one to
   two ideas each; 5 real JDs in `private/targets/jds/` for profile_rewrite and outreach cases;
   the 225 scraped market posts as reach-post seeds.
2. **Synthetic from real seeds** — paraphrase and difficulty-vary the above. Label by hand.
3. **Migrated** — the 11 existing `golden.jsonl` cases, re-labelled into the new schema.

No LLM-generated cases beyond the two adversarial ones. There is enough real material here.

### 4.3 Case schema

```json
{
  "id": "authority-source-01",
  "kind": "happy",
  "intent_expected": "authority",
  "idea": "...",
  "expected_story_ids": ["story-07"],
  "allowed_facts": ["a verified delivery metric"],
  "planted_claims": [],
  "planted_claim_class": null,
  "expected_terminal_node": "hitl",
  "note": "why this case exists"
}
```

### 4.4 The honest cost

Hand-labelling `expected_story_ids` for 44 cases against 9 stories is roughly 3 to 4 hours and it
cannot be delegated to a model. It is the single step that makes every downstream number mean
something. Budget it as a full half-day, not as an afternoon's overhead.

### 4.5 Versioning

The private reviewer dataset is the source of truth. Record its SHA-256 in the public report and
provide the package directly to reviewers. Tag it `v1` and **do not change it between the baseline
and post-improvement runs** — if the dataset moves, the delta is meaningless.

---

## 5. Phase 2 — Instrumentation

Work items, in order. Do not start Phase 3 until item 4 passes.

1. **Declare the dependency.** `uv add langsmith`. It arrives transitively via LangGraph today,
   which means it is unpinned.
2. **Fix trace loss on timeout.** In `_live_case_worker`, wrap the body in `try/finally` calling
   `langsmith.utils.wait_for_all_tracers()`. On the parent side, send `SIGINT` first, allow ~5s
   for the flush, then `terminate()`. Verify by forcing a timeout and confirming the partial trace
   appears in LangSmith.
3. **Make `gate` visible.** Wrap `deterministic_gate` with `@traceable(name="gate")` so the
   claims, voice and confidential reports appear as a child run's output. This is the trace
   evidence the submission depends on.
4. **Verify exactly one trace end to end.** One live case. Confirm in the LangSmith UI:
   parent run named `case:{id}`; child runs for profile_memory, intake_router, ground (with the
   ReAct tool calls nested beneath it), write, gate, critique; token counts and cost on every LLM
   run; the full metadata block present. Fix tracing before building anything else.
5. **Add prompt versions.** No prompt version constant exists today. Add `WRITE_PROMPT_VERSION`,
   `ROUTER_PROMPT_VERSION`, `CRITIQUE_PROMPT_VERSION` and emit them in metadata. Bump per
   improvement. Without this the comparison view cannot attribute a delta to a change.
6. **Write evaluators** as functions over `(run, example)`, registered against the private
   reviewer package. Five code-based, one LLM-as-judge.
7. **Build the live runner.** New `evals/run_live.py` using `client.evaluate(target, data,
   evaluators, max_concurrency=4)`. The target is a thin wrapper around the existing `run_case`
   logic: invoke the graph, read `graph.get_state()`, return a dict containing draft, stories,
   claims_report, voice_report, next node and node path. The `interrupt()` is not an obstacle —
   `run_case` already handles it by inspecting `snapshot.next`.

Leave `evals/run.py` alone as the offline CI gate.

### Metadata schema (single source, applied to every run)

```python
config = {
    "configurable": {"thread_id": tid},
    "run_name": f"case:{case['id']}",
    "tags": [case["kind"], case["intent_expected"], run_group],
    "metadata": {
        "case_id": case["id"],
        "kind": case["kind"],
        "intent_expected": case["intent_expected"],
        "prompt_version": WRITE_PROMPT_VERSION,
        "agent_sha": git_sha(),
        "dataset_version": "v1",
        "run_group": run_group,
        "writer_model": config.MODEL_WRITER,
        "router_model": config.MODEL_ROUTER,
        "offline": False,
    },
}
```

Identical schema for baseline and improved runs. That is what makes the comparison view work.

---

## 6. Phase 3 — Baseline and failure analysis

1. **Pilot 5 cases live.** Confirm traces, metadata, token counts and cost. Then, and only then,
   set the latency and cost pass bars from observed numbers.
2. **Full baseline.** 44 private cases, `run_group=baseline`, `max_concurrency=4`. At roughly 140s per
   case that is about 26 minutes of wall clock. Watch provider rate limits; drop to 2 if throttled.
3. **Cluster before fixing.** Export the run, group failures by (failed metric x intent x kind).
   Twenty failures are usually two or three root causes.

Predicted clusters, from what the code already shows:

| Cluster | Root cause | Expected cases | Rework cost per occurrence |
| --- | --- | --- | --- |
| **C1 — intent fall-through** | `profile_rewrite` and `outreach` are not wired into `build_graph`; both intents route to the standard drafting path and produce the wrong output shape. | 7 to 9 | Full manual rewrite, 20 to 40 min |
| **C2 — wrong story retrieved** | Clustering on full post text groups by topic, not structure; retrieval returns a topically adjacent but factually wrong story. | 5 to 10 | Re-prompt and re-review, 5 to 10 min |
| **C3 — latency tail** | ReAct iterations plus the 25s intel timeout, never isolated. | tail cases | Attention cost, not rework |

Report one linked trace per cluster, connected to its case through `case_id` metadata.

---

## 7. Phase 4 — Four improvements

**Pre-register the predicted delta before running.** Write the prediction down first, or you will
rationalise whatever number you get.

| # | Lever | Specific change | Targets | Predicted delta | Stated risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Control flow | Wire `profile_rewrite` and `outreach` nodes into `build_graph`; route on `intent` after the router. | C1 | Intent completion 60% to 100% | Low. Both nodes already exist and are tested. |
| 2 | Retrieval | Re-cluster on the structural voice features already computed for the fingerprint (`cluster.py structure`) instead of full-text embeddings; rank stories by metric-overlap with the idea, not embedding similarity alone. | C2 | Story top-1 plus 15pp | May regress topically-obvious happy-path cases. |
| 3 | Guardrail | Second advisory semantic detector for hedged quantities — numeral-word plus hedge-lexicon regex first, LLM extractor only if that underperforms. | Hedged leak class | Hedged recall 0% to at or above 70% | Plus ~$0.002 per run, plus ~2s. False positives on clean drafts are the real risk — watch precision. |
| 4 | Latency | Run `ground` retrieval and the market-brief fetch concurrently; cap ReAct iterations at 6; cache the fingerprint load. | C3 | p95 minus 40% | Capping iterations may cost 5pp of story top-1. This is a genuine trade and must be reported as one. |

Improvements 1 and 3 have the highest certainty of a measurable delta. If time compresses, do
those two.

Re-run the **identical dataset version** with the **identical metadata schema**,
`run_group=improved`, then use the LangSmith comparison view for per-metric and per-case deltas.

**If an improvement regresses a metric, report the regression.** Negative deltas are the signal
the assignment is actually asking for.

---

## 8. Production monitoring (for the What Is Next section)

| Signal | Threshold | Why it matters here |
| --- | --- | --- |
| Claim leak | Any single unlabelled ungrounded claim reaching `hitl` | This is the one failure that damages the user's credibility publicly. Alert immediately, no window. |
| Voice drift | Mean \|z\| rises above 1.5 over a 7-day rolling window | The fingerprint ages as the user's real writing changes; drift means the fingerprint needs a refresh, not the agent. |
| Cost spike | p95 cost per run above 1.25x budget over 24h | Historically a ReAct loop or an uncached intel fetch. |
| Latency | p95 above 180s on more than 5% of runs | Guardrail only, not a headline. |
| Tool failure | Any single read tool above 5% failure over 1h | Apify and the intel MCP are the external dependencies. |
| Degradation reasons | Rate of any `degradation_reasons` entry above 2x baseline | The system degrades quietly by design; this is the only way that becomes visible. |

---

## 9. Schedule

| Day | Work | Output |
| --- | --- | --- |
| 1 | Fill the framework. Fix trace loss. Wrap `gate` as traceable. Add prompt versions. Verify one trace. | One verified LangSmith trace |
| 2 | Build and hand-label 44 cases. Push to LangSmith, tag `v1`. | `evals/golden_v2.jsonl` plus dataset |
| 3 | Write six evaluators. Pilot 5 live. Set cost and latency bars. Run full baseline. | Baseline numbers plus project link |
| 4 | Cluster failures. Implement improvements 1, 2, 3. | Three linked failure traces |
| 5 | Improvement 4. Post-improvement run. Comparison. Write report. Record Loom. | Full submission |

**Cut line if compressed:** 30 cases (keep the full intent spread, drop synthetic variants),
improvements 1 and 3 only, skip 2 and 4. That still yields a real, defensible measured delta.

---

## 10. Deliverables checklist

- [ ] Report with the framework table fully filled
- [ ] `evals/golden_v2.jsonl` plus LangSmith dataset `lco-golden` tagged `v1`
- [ ] LangSmith project link, `lco-eval`
- [ ] One fully verified trace showing all child runs plus the `gate` node plus metadata
- [ ] One trace per failure cluster, linked to its case via `case_id`
- [ ] Baseline and post-improvement runs, plus the comparison view
- [ ] Per-improvement table: lever, change, cluster targeted, predicted delta, measured delta
- [ ] Human-minutes side metric on the 10-case subset
- [ ] Loom, roughly 5 minutes: what changed, what improved, what still fails

## 11. Public privacy boundary

The public repository contains aggregate methodology and findings only. The reviewer dataset,
per-case outputs, trace evidence, source mapping, and target material are supplied directly to
reviewers. Record the dataset SHA-256 in the report; do not publish verbatim allowed facts,
per-case draft text, source identifiers, or target names.
