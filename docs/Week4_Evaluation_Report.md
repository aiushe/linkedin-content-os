# Week 4 Evaluation Report — LinkedIn Content OS

## 1. Evaluation one-liner

I will measure claim-leak rate, story-retrieval accuracy, voice distance, intent task-completion,
and cost-per-delivered-draft on the LinkedIn Content OS drafting agent. The fixed 44-case reviewer
dataset spans all six router intents. Code-based evaluators assess claims, voice, trajectory,
latency, and cost; an LLM-as-judge grounding-faithfulness score is calibrated against 15
hand-reviewed cases. The before/after comparison uses an unchanged dataset version and identical
run metadata.

## 2. Evaluation framework

| Field | Answer |
| --- | --- |
| Agent under test | LinkedIn Content OS drafting agent (`agent/graph.py`). |
| User outcome | A grounded, voice-aware LinkedIn draft with every factual claim visibly labelled for quick human approval. |
| Metrics | Claim-leak rate; story top-1/top-3; mean absolute voice z; intent task completion; cost per delivered draft and p95 latency. |
| Judge method | Code evaluators plus a calibrated LLM-as-judge grounding-faithfulness evaluator. |
| Golden dataset | Private reviewer package: 44 hand-reviewed cases, version `v1`; SHA-256 recorded below. |
| Pass bar | Zero numeric leaks; hedged leak at or below 30%; top-1 at or above 85%; mean voice \|z\| at or below 1.0; intent completion 100%; mean locally priced cost at or below $0.002384 per delivered draft; p95 latency at or below 60.01 s. |
| Instrumentation | One parent trace per case with node-level child runs, versioned prompts, run-group tags, and outcome metadata. |
| Baseline | TBD. |
| Failure analysis | TBD. |
| Improvements | Control-flow wiring, hedged-quantity detection, retrieval ranking, and latency controls; all predictions will be registered before measurement. |
| Post-improvement run | TBD. |
| What is next | TBD. |

## 3. Metric definitions and judges

| Metric | Definition | Judge |
| --- | --- | --- |
| Claim leak | Ungrounded claims in the draft missing from `claims_report.unresolved`, split by numeric and hedged class. | Code + case labels |
| Story retrieval | Expected first anonymized story label equals retrieved first label; top-3 is secondary. | Exact match |
| Voice distance | Mean absolute z across scored fingerprint features. | Code |
| Intent completion | Observed trajectory reaches the labelled intent's expected terminal node/path. | Code |
| Efficiency | Summed run cost per draft that reached `hitl`, plus elapsed latency. | Code + trace metadata |
| Grounding faithfulness | Every factual statement traces to retrieved evidence or the claim allowlist. | Calibrated LLM judge |

## 4. Golden dataset and labelling

The private reviewer package contains 44 cases across authority, reach, comment, profile rewrite,
outreach, and out-of-scope requests. Labels were hand-reviewed. The story-retrieval denominator
is `n=21`, because cases without an expected source are excluded; every reported percentage must
include `n=21` and a confidence interval.

## 5. Instrumentation and privacy boundary

The graph records one `case:{id}` chain with nested node runs, including a `gate` child chain.
Every case carries case, dataset, model, prompt-version, and run-group metadata; its completed
state also yields error classes, error nodes, and degradation reasons.

Two tracing defects were addressed: worker timeout now provides a graceful interrupt and tracer
flush window, and the deterministic gate is visible as a child run. A synthetic-fixture acceptance
run recorded the full node hierarchy, metadata, and token usage. Nested child-cost display remains
a packaging follow-up; the configured writer has no local price and is reported as zero rather
than inferred.

The dataset and per-case results are withheld from the public repository as a deliberate privacy
boundary. Public materials report aggregate methods and findings only: no verbatim allowed facts,
per-case draft text, real source identifiers, target names, or trace links are published. Dataset
SHA-256: `31947c6fb6d5b13ac706a8fa054f46f47a6d9048e5e147842a60acf0a01bc0de`. The matching
dataset, results, and private reviewer appendix are provided directly to reviewers. The five-case
pilot set the latency bar at 60.01 seconds (1.5x observed p95 of 40.00 seconds) and the locally
priced cost bar at $0.002384 per delivered draft (1.5x observed mean of $0.001590).

## 6. Baseline results

The fixed v1 baseline completed all 44 cases. All 44 produced a draft and reached the human
review interrupt. Aggregate results are shown below; per-case outputs remain in the local reviewer
package.

| Metric | Baseline | Basis | Pass bar |
| --- | ---: | --- | ---: |
| Story top-1 | 52.38% (11/21; 95% CI 32.37–71.66%) | 21 reviewed story-labelled cases | 85% |
| Story top-3 | 76.19% (16/21) | Same denominator | Secondary |
| Mean voice \|z\| | 1.925 | 44 generated drafts | 1.0 |
| Intent completion | 31.82% (14/44) | Exact labelled trajectory | 100% |
| Draft delivered | 100% (44/44) | Draft plus `hitl` interrupt | Informational |
| Numeric planted-claim leak | 0% | 3 numeric-labelled cases | 0% |
| Hedged planted-claim leak | 0% | 1 hedged-labelled case | at or below 30% |
| p95 latency | 38.19 s | 44 completed cases | 60.01 s |
| Mean locally priced cost | $0.000989 | Delivered drafts | $0.002384 |

The total locally priced baseline cost was $0.043524. Provider usage metadata contained one
zero-usage nested child run, which remains explicitly unpriced rather than being filled with an
estimate. The grounding-faithfulness judge was not run because the required human calibration
labels do not yet exist.

## 7. Failure analysis

Failures were clustered by failed metric, labelled intent, and case kind from the private run
export. No individual corpus content or trace link is reproduced here.

| Cluster | Result | Frequency | Human-rework estimate | Evidence |
| --- | --- | ---: | ---: | --- |
| C1 — profile/outreach fall-through | Confirmed. All 12 labelled profile-rewrite or outreach cases entered the standard drafting path even when their router intent was correct. | 12/44 | 20–40 min per occurrence, modeled pending human review | Private trace metadata and local trajectory export |
| C2 — wrong story retrieved | Confirmed as a quality failure (10/21 top-1 misses), but the predicted full-text clustering cause is refuted: structural clustering was already present. The remaining issue is transparent lexical ranking with weak discrimination. | 10/21 eligible | 5–10 min per occurrence, modeled pending human review | Private run export |
| C3 — latency tail | Refuted. No baseline case exceeded the pilot-derived 60.01 s guardrail; p95 was 38.19 s. | 0/44 | Not applicable | Private run export |
| U1 — routing/decline gap | Unpredicted. The live router matched the expected intent on 31/44 cases, and none of the five out-of-scope cases met the required graceful-decline behavior. | 18 trajectory failures after separating C1 | Human review required; no measured minutes yet | Private run export |
| U2 — voice distance | Unpredicted. All 44 generated drafts exceeded the mean \|z\| pass bar. | 44/44 | Human voice review required | Private run export |

The rework-minute figures are transparent planning estimates, not human-observed measurements.
The 10-case human-review subset is prepared separately and is the required next input to replace
those estimates with observed review time.

## 8. Improvements and measured deltas

| Lever | Change | Cluster targeted | Predicted delta | Measured delta |
| --- | --- | --- | --- | --- |
| Control flow | Routed `profile_rewrite` and `outreach` after intake instead of falling through to drafting. | C1 | Intent completion approximately 60% to 100%; +12 exact-trajectory cases, with router errors unchanged. | Intent completion **31.82% → 59.09%** (+27.27pp; exactly 12 corrected paths). Missed the rounded 60% prediction by 0.91pp. Story top-1 regressed **52.38% → 47.62%** (-4.76pp). Draft-delivery rate fell **100% → 68.18%** because the two newly correct read-only workflows intentionally terminate without a draft; this makes the generic delivered-draft metric inapplicable to those endpoints. |
| Guardrail | **Pre-registered before `improved-2`:** add an advisory hedge-plus-number-word regex alongside the existing extractor. | Hedged claims | Direct hedge-detection recall 0% to at least 70%, with no clean-fixture false positives. The one live hedged case is retained as a secondary outcome. | TBD |
| Retrieval | TBD | Story top-1 +15pp | TBD | TBD |
| Latency | TBD | C3 | p95 latency -40% | TBD |

## 9. Human-minutes review subset

TBD after human review.

## 10. Production monitoring

| Signal | Threshold |
| --- | --- |
| Claim leak | Any unlabelled ungrounded claim reaching `hitl`. |
| Voice drift | Mean \|z\| above 1.5 over seven days. |
| Cost spike | p95 cost above 1.25x budget over 24 hours. |
| Latency | p95 above 180 seconds on more than 5% of runs. |
| Tool failure | Any read tool above 5% failure over one hour. |
| Degradation reasons | Any reason exceeds twice its baseline rate. |

## 11. What is next

TBD from the measured remaining failure mode.

## 12. Limitations

- Aggregate reporting deliberately omits the private reviewer package and trace evidence.
- Latency and cost bars remain TBD until a privacy-safe pilot establishes current model behaviour.
- The grounding judge remains unavailable until the 15 human calibration labels are supplied.
