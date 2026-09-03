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
| Pass bar | Zero numeric leaks; hedged leak at or below 30%; top-1 at or above 85%; mean voice \|z\| at or below 1.0; intent completion 100%; cost and latency bars TBD after pilot. |
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

The graph records one `case:{id}` trace with nested node runs, including a `gate` child chain.
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
dataset, results, and private reviewer appendix are provided directly to reviewers.

## 6. Baseline results

TBD.

## 7. Failure analysis

TBD.

## 8. Improvements and measured deltas

| Lever | Change | Cluster targeted | Predicted delta | Measured delta |
| --- | --- | --- | --- | --- |
| Control flow | TBD | C1 | Intent completion 60% to 100% | TBD |
| Guardrail | TBD | Hedged claims | Hedged recall 0% to at least 70% | TBD |
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
