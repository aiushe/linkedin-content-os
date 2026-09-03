# Week 4 execution log

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
