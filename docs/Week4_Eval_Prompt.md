# Week 4 execution prompt

Paste the block below into Claude Code, opened in the repo root. It is self-contained.

---

You are executing the Week 4 evaluation project for this repository. Read `CLAUDE.md`,
`README.md`, `docs/Week3_Project_Documentation.md` and `docs/Week4_Eval_Plan.md` before you
begin. `docs/Week4_Eval_Plan.md` is the design; this prompt is the execution order. Where they
disagree, this prompt wins.

Work autonomously through every phase. There is exactly ONE hard stop, in Phase 2. Do not stop
anywhere else to ask permission; record decisions and keep going.

## 0. What this project is

I am evaluating my own Week 3 agent — the LinkedIn Content OS drafting agent in `agent/graph.py`.
This is an EVALUATION project, not a build project. Every code change you make exists to measure
the agent or to fix a measured failure. Do not add features.

The submission is graded on **measured delta**: baseline numbers, failure analysis, targeted
improvements, re-measured numbers. A change with no before/after number does not count.

## 1. Non-negotiables

1. Obey every rule in `CLAUDE.md`. In particular: never write into `private/` except the
   truth-table row flow that already exists, and never put `#` comments on command lines.
2. Never commit `.env`, `private/`, `drafts/`, `intel/` (except `intel/reports/`), or any key.
   Check `git status` before every commit.
3. Do not change `evals/run.py` behaviour except the tracer-flush fix in Phase 1. It stays the
   fast offline CI gate. All new live evaluation goes in new files.
4. Do not modify the golden dataset after the baseline run. If you find a bad case, record it in
   the report as a limitation; do not silently fix it. A dataset that moves between runs makes
   the delta meaningless.
5. Run `uv run pytest -q` and `uv run ruff check . --exclude .venv` after every phase that
   touches code. Both must pass before you move on.
6. Commit at the end of each phase with a message naming the phase.
7. When something blocks you, write the blocker into `docs/Week4_LOG.md` with what you tried, pick
   the least destructive path forward, and continue. Do not stall.

## 2. Deliverables manifest — check this at the end of every phase

The submission is not complete until all nine exist:

1. `docs/Week4_Evaluation_Report.md` and an exported `.docx` — the solution doc.
2. `evals/golden_v2.jsonl` — 44 hand-verified cases.
3. LangSmith dataset `lco-golden`, tagged `v1`.
4. LangSmith project `lco-eval-w4` with baseline and improved runs.
5. `evals/results/week4_results.xlsx` — per-case spreadsheet, three tabs.
6. `evals/week4_eval.ipynb` — executed notebook with outputs saved.
7. `docs/week4_traces/` — screenshots: one full verified trace, one per failure cluster.
8. `docs/Week4_Loom_Script.md` — a written five-minute walkthrough script.
9. `docs/Week4_LOG.md` — running decision and blocker log, written as you go.

## 3. Environment facts

Already configured in `.env`: `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `NEBIUS_API_KEY`,
`LLM_BASE_URL=https://api.tokenfactory.nebius.com/v1`,
`MODEL_WRITER=Qwen/Qwen3.5-397B-A17B`, `MODEL_ROUTER=Qwen/Qwen3-30B-A3B-Instruct-2507`.

All live evaluation runs must set `LANGSMITH_PROJECT=lco-eval-w4` so eval traces never mix with
day-to-day app usage. Set it in the runner process, not in `.env`.

Corpus policy for this project: run against the REAL corpus in `private/`, with the
confidential-terms gate unconfigured and Mem0 disabled (`MEM0_ENABLED=false` in the runner
environment), so no employer-sensitive text and no approved personal memory reaches LangSmith
traces. State this policy in the report.

---

## PHASE 1 — Instrumentation hardening

Nothing else happens until one trace is verifiably correct.

### 1.1 Pin the dependency

`uv add langsmith`. It currently arrives transitively through LangGraph, which means it is
unpinned.

### 1.2 Fix trace loss on timeout

`evals/run.py:run_live_case` calls `process.terminate()` when a case outlives its deadline.
LangSmith flushes traces from a background thread, and SIGTERM discards whatever is queued — so
every timed-out case, which is exactly the set of failures I care most about, currently reaches
LangSmith as nothing.

Fix both sides:

- In `_live_case_worker`, wrap the body in `try/finally` and call
  `from langsmith.utils import wait_for_all_tracers; wait_for_all_tracers()` in the `finally`.
- In `run_live_case`, on deadline send `SIGINT` first, `join(5)` to let the flush complete, and
  only then `terminate()`.

Verify it: temporarily set `EVAL_CASE_TIMEOUT_SECONDS=5`, run one live case, confirm a partial
trace appears in LangSmith, then restore the timeout. Record the evidence in
`docs/Week4_LOG.md`.

### 1.3 Make the deterministic gate visible

`deterministic_gate` in `agent/graph.py` is pure Python, so it does not appear in the trace tree
at all. The three advisory checks are the most safety-relevant component in this system and they
are currently invisible in exactly the evidence that is supposed to prove they work.

Wrap it with `@traceable(name="gate", run_type="chain")` so the voice, claims and confidential
reports appear as that child run's output.

### 1.4 Add prompt versions

No prompt version constant exists anywhere in the repo. Without one, the LangSmith comparison
view cannot attribute a delta to a change.

Add module-level constants and emit them in run metadata:

- `agent/nodes/write.py` -> `WRITE_PROMPT_VERSION = "w3-baseline"`
- `agent/nodes/router.py` -> `ROUTER_PROMPT_VERSION = "w3-baseline"`
- `agent/nodes/critique.py` -> `CRITIQUE_PROMPT_VERSION = "w3-baseline"`

Bump the relevant one to `w4-imp{n}` in Phase 6 whenever you change that prompt.

### 1.5 Surface errors and degradation in metadata

Phase 2 of the assignment explicitly requires errors visible in LangSmith. This agent has a
five-class error taxonomy and a `degradation_reasons` list on state — a genuine strength that is
currently unreportable. At the end of each case, write `error_classes`, `error_nodes` and
`degradation_reasons` into the run's metadata.

### 1.6 The metadata schema

Define this once, in `evals/metadata.py`, and use it for every run in every phase. Baseline and
improved runs MUST use an identical schema or the comparison view is worthless.

```python
def run_config(case, run_group, *, offline=False):
    return {
        "configurable": {"thread_id": f"eval-{case['id']}"},
        "run_name": f"case:{case['id']}",
        "tags": [case["kind"], case["intent_expected"], run_group],
        "metadata": {
            "case_id":         case["id"],
            "kind":            case["kind"],
            "intent_expected": case["intent_expected"],
            "prompt_version":  WRITE_PROMPT_VERSION,
            "router_prompt_version": ROUTER_PROMPT_VERSION,
            "agent_sha":       git_sha(),
            "dataset_version": "v1",
            "run_group":       run_group,
            "writer_model":    os.environ.get("MODEL_WRITER"),
            "router_model":    os.environ.get("MODEL_ROUTER"),
            "offline":         offline,
        },
    }
```

### 1.7 Verify exactly one trace — acceptance gate

Run ONE live case end to end. Open it in LangSmith and confirm every item:

- Parent run named `case:{id}` in project `lco-eval-w4`
- Child runs for `profile_memory`, `intake_router`, `ground`, `write`, `gate`, `critique`
- The ReAct tool calls nested beneath `ground`, not flattened to the top level
- Token counts and cost on every LLM child run
- The complete metadata block from 1.6
- Inputs and outputs readable on each child run

Screenshot it to `docs/week4_traces/01-verified-trace.png` and record the run URL in
`docs/Week4_LOG.md`. **Do not proceed until all six items pass.**

### 1.8 Write the report skeleton now

Create `docs/Week4_Evaluation_Report.md` with the full section structure and the framework table
from `docs/Week4_Eval_Plan.md` filled in, leaving numeric blanks as `TBD`. Fill the blanks as
runs land. Do not leave report-writing to the last day — that is the day it slips.

Then: `pytest`, `ruff`, commit.

---

## PHASE 2 — Golden dataset, 44 cases

### 2.1 Read the private reviewer corpus first

Before writing a single case, read and take notes on:

- All 9 private source records: `story-01`, `story-02`, `story-03`, `story-04`, `story-05`,
  `story-06`, `story-07`, `story-08`, and `story-09`
- The private claim allowlist
- `private/identity/voice.md`, `positioning.md`, `pillars.md`, `icp.md`
- The 4 drafts in `drafts/queue/`
- The 5 JDs in `private/targets/jds/`
- `intel/reports/top-posts.md` and `template-library.md`

Cases must be derived from this real material. Do not invent a career.

### 2.2 Case schema

```json
{
  "id": "authority-source-01",
  "kind": "happy",
  "intent_expected": "authority",
  "idea": "the rough thought a user would actually type",
  "expected_story_ids": ["story-07"],
  "allowed_facts": ["a verified delivery metric"],
  "planted_claims": [],
  "planted_claim_class": null,
  "expected_terminal_node": "hitl",
  "source": "real | paraphrase | migrated | synthetic",
  "note": "why this case exists"
}
```

`planted_claim_class` is one of `numeric`, `hedged`, `superlative`, `attribution`, or null.

### 2.3 Distribution — hit both cuts exactly

By intent (44 total): `authority` 12, `reach` 8, `comment` 7, `profile_rewrite` 6,
`outreach` 6, `out_of_scope` 5.

By kind: `happy` 22 (50%), `edge` 13 (30%), `known_failure` 7 (15%), `adversarial` 2 (5%).

- **happy** — well-formed ideas, one clearly correct source story each.
- **edge** — ambiguous intent, two equally plausible stories, partial data, an idea with no
  supporting story at all, very short input, very long input, out-of-scope requests that should
  be handled gracefully rather than refused.
- **known_failure** — hedged quantities with no digit ("roughly half", "most of the team");
  `profile_rewrite` and `outreach` cases, which currently cannot pass because those nodes are not
  wired into `build_graph`; topic-similar-but-wrong-story traps built from the two deterministic
  stories, which are the pair most likely to be confused; plus the existing `poison-laundering`
  case migrated across.
- **adversarial** — exactly two: a prompt injection embedded in the idea text, and an explicit
  instruction to skip the claim check.

Migrate all 11 cases from `evals/golden.jsonl` into the new schema and count them toward the
totals. Mark them `"source": "migrated"`.

Cap `"source": "synthetic"` at 8 cases. Everything else must trace to real corpus material.

### 2.4 HARD STOP — hand this to me for review

Write `evals/golden_v2.jsonl` and, alongside it, a human-readable review table at
`evals/golden_v2_review.md` with one row per case:

| # | id | kind | intent | idea (truncated 80 chars) | expected_story_ids | planted | source | note |

Then STOP and tell me the review table is ready. Say explicitly that I need to check
`expected_story_ids` on every row, because that label is the ground truth for the retrieval
metric and a model-generated label is not ground truth. Wait for my corrections before
proceeding. This is the only stop in the whole run.

### 2.5 After I return corrections

Apply them exactly. Do not argue with a label I changed. Then prepare the private reviewer package:

```python
record_dataset_sha256("private reviewer dataset, v1")
```

Tag the dataset version `v1`. Record the dataset SHA-256 in `docs/Week4_LOG.md`; provide the
dataset directly to reviewers rather than committing or publishing it.

Then: `pytest`, `ruff`, commit.

---

## PHASE 3 — Evaluators

Write six evaluators in `evals/evaluators.py`, each taking `(run, example)` and returning a
LangSmith score dict.

1. **`claim_leak`** — code. Ungrounded claims present in the final draft that do NOT appear in
   `claims_report.unresolved`, divided by total ungrounded claims present. Return the rate plus a
   `class` field of `numeric` or `hedged` so the two can be reported separately. Grounded on the
   case's `allowed_facts` and `planted_claims` labels.
2. **`story_top1`** — exact match. `example.expected_story_ids[0] == run.outputs["stories"][0]["id"]`.
   Also emit `story_top3` as a secondary score.
3. **`voice_distance`** — code. Mean absolute z across `scored_features` from
   `pipeline/voice`. Continuous. Do NOT use the pass/warn/revise verdict — it is derived from
   `VOICE_Z_THRESHOLD` and moves whenever that threshold is tuned, which makes it useless as a
   metric.
4. **`intent_completion`** — trajectory. Compare the observed node path against the expected path
   for `intent_expected`. `profile_rewrite` and `outreach` are expected to FAIL at baseline;
   that is the point.
5. **`efficiency`** — code, from run metadata. Cost per delivered draft (a case counts as
   delivered only if it produced a draft AND reached `hitl`), plus latency.
6. **`grounding_faithfulness`** — LLM-as-judge. Rubric: does every factual statement in the draft
   trace to a retrieved story or a truth-table row? Run it only on the 15-case calibration
   subset. Hand-label those 15 yourself first, then report judge/human agreement in the report.
   An uncalibrated LLM judge is decoration.

Add unit tests in `tests/test_evaluators.py` covering at least one pass and one fail per
evaluator. Then: `pytest`, `ruff`, commit.

---

## PHASE 4 — Pilot, then baseline

### 4.1 Build the live runner

`evals/run_live.py` using `client.evaluate(target, data="lco-golden", evaluators=[...],
max_concurrency=4, metadata=...)`.

The target is a thin wrapper around the existing `run_case` logic in `evals/run.py`: invoke the
graph, read `graph.get_state()`, return a dict with `draft`, `stories`, `claims_report`,
`voice_report`, `next` and `node_path`. The `interrupt()` is not an obstacle — `run_case`
already handles it by inspecting `snapshot.next`.

Accept `--run-group` (`baseline` or `improved-N`) and `--limit N` on the command line.

### 4.2 Pilot five cases

Run 5 cases live. Confirm traces, metadata, token counts and cost all land. **Then, and only
then, set the latency and cost pass bars** from the observed numbers and write them into the
report. The prior figures in the Week 3 doc predate the writer model swap, so any number quoted
from them today is fiction. Set them at roughly 1.5x observed p95 and 1.5x observed mean cost.

### 4.3 Full baseline

Run all 44 with `--run-group baseline`. Roughly 26 minutes of wall clock at `max_concurrency=4`.
Drop to 2 if the provider throttles. Print an estimated cost before starting and record the
actual afterward.

Write the numbers into the report. Record the LangSmith run URL.

Then: commit.

---

## PHASE 5 — Failure analysis

Export the baseline run and cluster failures by *failed metric x intent x kind*. Twenty failures
are usually two or three root causes, not twenty bugs.

The plan predicts three clusters; confirm or refute each against the data rather than assuming:

- **C1 intent fall-through** — `profile_rewrite` and `outreach` are implemented in
  `agent/nodes/` but never added to `build_graph`, so both intents fall through to the standard
  drafting path and produce the wrong output shape.
- **C2 wrong story retrieved** — `pipeline/cluster.py` clusters on full post text, which groups
  by topic rather than structure, so retrieval returns a topically adjacent but factually wrong
  story.
- **C3 latency tail** — ReAct iterations plus the 25s intel timeout, never isolated.

For each confirmed cluster record: frequency, one linked trace URL, a screenshot to
`docs/week4_traces/`, and the cost per occurrence expressed in human rework minutes — not in
tokens. The user outcome this agent serves is replacing 45 to 90 minutes of manual work, so
rework minutes is the honest unit.

If a predicted cluster does not appear in the data, say so in the report. If an unpredicted one
does, that is the more interesting finding.

---

## PHASE 6 — Four improvements

**Pre-register every predicted delta in the report BEFORE running the improvement.** Commit that
prediction. Otherwise you will rationalise whatever number comes back.

Implement in this order, because 1 and 3 have the highest certainty of a measurable delta:

**Improvement 1 — control flow.** Wire `profile_rewrite` and `outreach` into `build_graph`,
routing on `intent` after `intake_router`. Predicted: intent completion 60% to 100%. Risk: low,
both nodes exist and are tested. Bump `ROUTER_PROMPT_VERSION` only if you change the prompt.

**Improvement 3 — guardrail.** Add a second advisory semantic detector for hedged quantities,
running alongside the regex extractor, never replacing it. Try a numeral-word plus hedge-lexicon
regex first; reach for an LLM extractor only if that underperforms. Predicted: hedged recall 0%
to at least 70%. Risk: false positives on clean drafts — watch precision on the 22 happy cases
and report it, because a noisy detector is how this tool gets deleted.

**Improvement 2 — retrieval.** Re-cluster on the structural voice features already computed for
the fingerprint instead of full-text embeddings, and rank stories by metric-overlap with the idea
rather than embedding similarity alone. Predicted: story top-1 plus 15pp. Risk: may regress
topically obvious happy-path cases.

**Improvement 4 — latency.** Run `ground` retrieval and the market-brief fetch concurrently, cap
ReAct iterations at 6, cache the fingerprint load. Predicted: p95 minus 40%. Risk: capping
iterations may cost 5pp of story top-1. That is a genuine trade and must be reported as one.

After each improvement, run the full 44 with `--run-group improved-{n}`, identical dataset
version and identical metadata schema. Record the per-metric delta.

**If an improvement makes a metric worse, report the regression and keep the change or revert it
on the evidence.** Negative deltas are the signal this assignment is actually asking for.
Silently dropping a failed improvement is the one thing that would make the whole submission
dishonest.

Then: `pytest`, `ruff`, commit each improvement separately with the measured delta in the commit
message.

---

## PHASE 7 — Packaging

This phase is where the marks are actually lost. Do all of it.

### 7.1 Results spreadsheet

`evals/results/week4_results.xlsx`, built from the LangSmith run exports. Three tabs:

- **baseline** — one row per case: `case_id, kind, intent_expected, intent_predicted,
  expected_story, predicted_story, story_top1, claim_leak, leak_class, voice_z,
  intent_completion, delivered, latency_s, cost_usd, error_classes, trace_url`
- **improved** — identical columns
- **delta** — per-metric aggregate baseline vs improved with the change, plus a per-case
  improved/regressed/unchanged column

A reviewer opens the spreadsheet before anything else. Make it scannable: freeze the header row,
tabular numbers, conditional formatting on the delta column.

### 7.2 Executed notebook

`evals/week4_eval.ipynb`. It is a presentation layer, NOT a second implementation — it imports
from `evals/run_live.py` and `evals/evaluators.py`. Cells: environment and config, dataset
upload, one verified trace, baseline run, failure clustering with a chart, each improvement, the
comparison, the delta table. Execute it and save it WITH outputs.

### 7.3 Trace evidence

`docs/week4_traces/` must contain, at minimum:

- `01-verified-trace.png` — the full child-run tree from Phase 1.7
- `02-metadata-panel.png` — the metadata block on that run
- `03-cluster-c1.png`, `04-cluster-c2.png`, `05-cluster-c3.png` — one per confirmed cluster
- `06-comparison-view.png` — baseline vs improved

**My LangSmith project is private by default.** A raw project link will 403 for a grader. Either
make the project public, or generate per-run public Share links for the traces cited in the
report — and include the screenshots regardless, as a fallback. Decide this before capturing, so
you capture the right frames.

### 7.4 The report

Complete `docs/Week4_Evaluation_Report.md`. Required sections:

1. The evaluation one-liner (the primer)
2. The framework table, every field filled
3. Metric definitions with judge method per metric
4. Golden dataset: source, size, scenario mix, labelling method — state plainly that cases were
   agent-drafted and hand-verified by me, and that `expected_story_ids` was corrected by hand
5. Instrumentation: trace design, metadata schema, and the two tracing defects found and fixed
   (lost traces on timeout, invisible `gate` node)
6. Baseline numbers with the project link and one verified trace
7. Failure analysis: three clusters, frequency, example trace each, cost in rework minutes
8. Improvements: lever, specific change, cluster targeted, predicted delta, measured delta — as a
   table, with regressions shown
9. The human-minutes side metric from the 10-case subset
10. Production monitoring strategy
11. What is next: top remaining failure mode, next hypothesis
12. Limitations, honestly stated

Then export to `docs/Week4_Evaluation_Report.docx` matching the format of the existing
`docs/Week3_Project_Documentation.docx`. Use the docx skill.

### 7.5 The human-minutes subset

Pick 10 cases spanning all intents. For each, count feedback/retry cycles before you would
approve, and estimate review minutes. This is manual and cannot be automated — prepare the 10
drafts in a single reviewable markdown file at `evals/results/human_review_subset.md` with a
blank table for me to fill, and tell me it is ready when you finish Phase 7.

### 7.6 Loom script

`docs/Week4_Loom_Script.md`, a written five-minute script with timings:

- 0:00-0:45 — the agent in one sentence, and why the obvious metric was saturated
- 0:45-1:45 — the golden dataset and how it was labelled
- 1:45-2:45 — one live trace walked through in LangSmith, pointing at the `gate` child run
- 2:45-4:00 — baseline numbers, the three failure clusters, one example trace
- 4:00-5:00 — the delta table including the regression, and what still fails

---

## 8. Definition of done

Do not report the project complete until every line is true:

- [ ] All nine deliverables in section 2 exist
- [ ] `uv run pytest -q` and `uv run ruff check . --exclude .venv` pass
- [ ] `uv run python evals/run.py` still passes as the offline gate
- [ ] `git status` shows no `.env`, `private/`, `drafts/` or key material staged
- [ ] The golden dataset is unchanged between baseline and improved runs
- [ ] Every improvement has a pre-registered prediction AND a measured delta
- [ ] At least one regression or failed hypothesis is reported honestly
- [ ] Every number in the report traces to a LangSmith run URL
- [ ] `docs/Week4_LOG.md` records every decision made without asking me

Finish by printing a summary: what improved, what regressed, what still fails, and the single
highest-value thing you would do with another week.
