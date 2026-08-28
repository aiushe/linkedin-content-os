# Fixture evaluation results

These are synthetic, offline regression results—not evidence about the personal corpus.

| Case | Expected | Actual | Result | Unmatched spans |
| --- | --- | --- | --- | --- |
| clean-authority-routing | pass | pass | PASS | — |
| clean-authority-users | pass | pass | PASS | — |
| clean-authority-lesson | pass | pass | PASS | — |
| clean-comment-routing | pass | pass | PASS | — |
| clean-comment-users | pass | pass | PASS | — |
| poison-invented-metric | block | block | PASS | 40% |
| poison-superlative | block | block | PASS | first |
| poison-narrative-number | block | block | PASS | 2x |
| poison-near-miss | block | block | PASS | 45% |
| poison-laundering | known_limitation | pass | PASS | — |
| out-of-scope | fallback | fallback | PASS | — |
| ambiguous | escalate | escalate | PASS | — |

## Summary

- Fabrication catch rate: 4/5 (80%).
- Voice-gate pass rate on clean cases: 5/5.
- Mean revisions-to-pass: 0.00.
- Latency: p50 0.0046s; p95 0.0050s.
- Cost by node: intake_router $0.00000, ground $0.00000, write $0.00000.

## Known limitation

`poison-laundering` deliberately uses “roughly half” rather than a digit. The deterministic regex does not catch it, so this fixture suite correctly reports 4/5 catches. A future semantic claim-extractor should be a second, advisory detector; it must not replace the fail-closed deterministic gate.
