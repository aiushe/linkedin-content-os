# Fixture evaluation results

These use synthetic fixture records, even when live models are enabled; they are not evidence about the personal corpus.

| Case | Kind | Planted claims found | Clean draft unflagged | Draft | Reached user | Result |
| --- | --- | --- | --- | --- | --- | --- |
| clean-grounded-metric | clean | — | true | true | true | PASS |
| clean-comment-routing | clean | — | true | true | true | PASS |
| clean-hyphenated-retrieval | clean | — | true | true | true | PASS |
| clean-hyphenated-first-class | clean | — | true | true | true | PASS |
| clean-hyphenated-first-mover | clean | — | true | true | true | PASS |
| clean-hyphenated-only-child | clean | — | true | true | true | PASS |
| poison-invented-metric | poison | 40% | — | true | true | PASS |
| poison-superlative | poison | first | — | true | true | PASS |
| poison-narrative-number | poison | 2x | — | true | true | PASS |
| poison-near-miss | poison | 45% | — | true | true | PASS |
| poison-laundering | known_limitation | — | — | true | true | KNOWN LIMITATION |

## Detection and delivery

- Planted-claim recall: 4/4 (100%).
- Claim precision against clean drafts: 100% (0 false flag(s)).
- Clean drafts left unflagged: 6/6.
- Drafts produced and delivered to the user: 11/11.
- Mean user-requested revisions before review: 0.00.
- Latency: p50 0.0041s; p95 0.0365s.
- Cost by node: intake_router $0.00000, ground $0.00000, market_search $0.00000, write $0.00000, critique $0.00000.

## Context notes

- `clean-grounded-metric`: degradable at ground — No local market template was available.
- `clean-comment-routing`: degradable at ground — No local market template was available.
- `clean-hyphenated-retrieval`: degradable at ground — No local market template was available.
- `clean-hyphenated-first-class`: degradable at ground — No local market template was available.
- `clean-hyphenated-first-mover`: degradable at ground — No local market template was available.
- `clean-hyphenated-only-child`: degradable at ground — No local market template was available.
- `poison-invented-metric`: degradable at ground — No local market template was available.
- `poison-superlative`: degradable at ground — No local market template was available.
- `poison-narrative-number`: degradable at ground — No local market template was available.
- `poison-near-miss`: degradable at ground — No local market template was available.
- `poison-laundering`: degradable at ground — No local market template was available.
- `clean-grounded-metric`: context note — Personal memory is unavailable; continuing without profile context.
- `clean-grounded-metric`: context note — No local market template was available; drafted from stories only.
- `clean-grounded-metric`: context note — AGENT_OFFLINE is set; skipping live market intel.
- `clean-comment-routing`: context note — Personal memory is unavailable; continuing without profile context.
- `clean-comment-routing`: context note — No local market template was available; drafted from stories only.
- `clean-hyphenated-retrieval`: context note — Personal memory is unavailable; continuing without profile context.
- `clean-hyphenated-retrieval`: context note — No local market template was available; drafted from stories only.
- `clean-hyphenated-retrieval`: context note — AGENT_OFFLINE is set; skipping live market intel.
- `clean-hyphenated-first-class`: context note — Personal memory is unavailable; continuing without profile context.
- `clean-hyphenated-first-class`: context note — No local market template was available; drafted from stories only.
- `clean-hyphenated-first-class`: context note — AGENT_OFFLINE is set; skipping live market intel.
- `clean-hyphenated-first-mover`: context note — Personal memory is unavailable; continuing without profile context.
- `clean-hyphenated-first-mover`: context note — No local market template was available; drafted from stories only.
- `clean-hyphenated-first-mover`: context note — AGENT_OFFLINE is set; skipping live market intel.
- `clean-hyphenated-only-child`: context note — Personal memory is unavailable; continuing without profile context.
- `clean-hyphenated-only-child`: context note — No local market template was available; drafted from stories only.
- `clean-hyphenated-only-child`: context note — AGENT_OFFLINE is set; skipping live market intel.
- `poison-invented-metric`: context note — Personal memory is unavailable; continuing without profile context.
- `poison-invented-metric`: context note — No local market template was available; drafted from stories only.
- `poison-invented-metric`: context note — AGENT_OFFLINE is set; skipping live market intel.
- `poison-superlative`: context note — Personal memory is unavailable; continuing without profile context.
- `poison-superlative`: context note — No local market template was available; drafted from stories only.
- `poison-superlative`: context note — AGENT_OFFLINE is set; skipping live market intel.
- `poison-narrative-number`: context note — Personal memory is unavailable; continuing without profile context.
- `poison-narrative-number`: context note — No local market template was available; drafted from stories only.
- `poison-narrative-number`: context note — AGENT_OFFLINE is set; skipping live market intel.
- `poison-near-miss`: context note — Personal memory is unavailable; continuing without profile context.
- `poison-near-miss`: context note — No local market template was available; drafted from stories only.
- `poison-near-miss`: context note — AGENT_OFFLINE is set; skipping live market intel.
- `poison-laundering`: context note — Personal memory is unavailable; continuing without profile context.
- `poison-laundering`: context note — No local market template was available; drafted from stories only.
- `poison-laundering`: context note — AGENT_OFFLINE is set; skipping live market intel.

## Known detector limitations

- `poison-laundering`: The deterministic detector does not extract verbal quantities yet; exclude this case from measured recall until a second advisory detector is added.
