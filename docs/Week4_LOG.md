# Week 4 execution log

## Phase 4 — live runner, pilot, and baseline

- 2026-09-02 governance decision: `CLAUDE.md` rule 6 now contains the scoped Week 4 exception
  authorising private LangSmith telemetry under `lco-eval-w4` only. The runner sets
  `MEM0_ENABLED=false`; the confidential-terms detector is disabled only for this evaluation
  process. Real-corpus trace sharing remains prohibited; any public trace evidence must use the
  fixture corpus.
- Created and tagged the fixed LangSmith dataset `lco-golden` at `v1`. Dataset URL (private,
  authenticated): `https://smith.langchain.com/o/6ff42efb-c081-40ba-aa4c-4fba377b79a3/datasets/6cef5ef7-c046-4e65-9eb2-a54a827d61b8`.
  It has 44 cases and matches SHA-256
  `31947c6fb6d5b13ac706a8fa054f46f47a6d9048e5e147842a60acf0a01bc0de`.
- Corrected pilot: 5/5 reached the human-review interrupt. Observed p95 latency was **40.00 s**
  and mean locally priced cost was **$0.001590**. The preregistered guardrail bars are therefore
  p95 latency at or below **60.01 s** and mean cost per delivered draft at or below **$0.002384**
  (both 1.5x pilot observations). Private pilot experiment URL:
  `https://smith.langchain.com/o/6ff42efb-c081-40ba-aa4c-4fba377b79a3/projects/p/1669af68-91e1-45a1-b03b-f17698d123b6`.
- API-only trace verification confirmed the per-case run name and Week 4 metadata schema, nested
  `ground` and `gate` children, and LLM token/cost fields. The platform wraps each evaluation
  target in a generic root run, so `case:{id}` is the named nested case chain rather than the
  outer experiment wrapper. One nested LLM child retained zero provider usage, an explicit known
  provider-metadata limitation rather than an inferred cost.
- Screenshot blocker: the in-app browser is unavailable in this environment. No trace screenshots
  were captured. Keep markdown/API trace summaries as the interim substitute and capture the
  required redacted screenshots manually from authenticated LangSmith before submission.

## Improvement 1 — preregistration

- Before changing the graph, registered the C1 prediction: adding the existing profile-rewrite
  and outreach branches after intake should convert the 12 known fall-through trajectories. This
  predicts intent completion rising from 31.82% to approximately 59.09% before any router or
  out-of-scope correction; no other metric is expected to improve directly.

## Improvement 1 — measured

- Private `improved-1` experiment completed all 44 fixed v1 cases. Intent completion rose from
  31.82% to 59.09% (+27.27pp, 12 trajectories), just below the rounded 60% prediction. Retrieval
  top-1 regressed from 52.38% to 47.62% (-4.76pp). The generic draft-delivery rate fell from 100%
  to 68.18% because the newly correct profile and outreach endpoints intentionally return
  preflight/manual guidance rather than a draft and `hitl`; this is retained and reported, not
  hidden. p95 latency fell 38.19 s to 21.65 s and mean locally priced delivered-draft cost fell
  $0.000989 to $0.000478, both incidental to avoiding the draft path. Private experiment URL:
  `https://smith.langchain.com/o/6ff42efb-c081-40ba-aa4c-4fba377b79a3/projects/p/07c2276d-f46c-4b13-a010-70b4675c8607`.

## Phase 1 — instrumentation hardening

- Added a direct LangSmith dependency so tracing is versioned by this project rather than only
  arriving transitively through LangGraph.
- Timeout handling now gives workers a graceful interrupt and a five-second tracer-flush window
  before termination. The installed SDK's compatible tracer flush path is used when its former
  utility import is absent.
- Wrapped the deterministic gate as a named trace child, added prompt-version constants, and
  added a single run-metadata schema with error and degradation context.
- Bounded writer completions at 1,200 tokens and disabled the provider's default reasoning channel
  after observing structured-output truncation. Local per-model usage and cost metadata is emitted
  before trace serialization; unknown model pricing remains an explicit zero rather than a guess.
- A synthetic-fixture acceptance run completed in 35.30 seconds with the expected graph-node tree,
  readable metadata, and nested grounding tool calls. LLM token usage and parent cost events were
  present; nested tool-call cost display remains partial. No public trace link or screenshot is
  retained in the repository.

## Phase 2 — private golden dataset harness

- Built a 44-case, hand-reviewed private evaluator dataset: 22 happy, 13 edge, 7 known-failure,
  and 2 adversarial cases across all six intents. It retains the 11 regression fixtures and stays
  within the synthetic-case cap.
- The reviewer correction pass reduced the story-retrieval population to **n=21**. Any direct
  reviewer report must state `n=21` and a confidence interval alongside a story-retrieval rate.
- The five out-of-scope cases require graceful decline and a handoff to the human-review node; a
  router classification alone does not pass.

## Phase 3 — evaluators

- Added code evaluators for claim leakage, story top-1/top-3, mean absolute voice z-distance,
  intent completion, delivered-draft efficiency, and calibration-only grounding faithfulness.
- Story cases without an expected source emit `not_applicable`, preserving the reviewed `n=21`
  denominator. The grounding judge remains inactive until the 15 human calibration labels exist.

## Public privacy boundary

- The public repository publishes aggregate methodology and aggregate findings only. The dataset,
  per-case results, trace evidence, reviewer mapping, target material, and outreach logs are
  deliberately withheld from Git as a privacy boundary.
- Dataset SHA-256: `31947c6fb6d5b13ac706a8fa054f46f47a6d9048e5e147842a60acf0a01bc0de`.
  The matching dataset and per-case results are provided directly to reviewers, along with the
  local reviewer appendix needed to interpret anonymized labels.
