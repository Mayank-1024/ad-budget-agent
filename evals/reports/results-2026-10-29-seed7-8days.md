# Eval report: results-2026-10-29-seed7-8days

- model: `claude-haiku-5-5, none`, store: `db (re-scored from Postgres)`, seed: 7, mode: `see policy`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 8 days
- generated: re-scored; eval window 2026-09-08 to 2026-09-15

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hold | 54,939 | 152,533 | 2.776 | 2.537 | 97,594 | 0 | 0 | 0 | 0 | 0 | 0.0 | n/a |
| roas_rule | 63,643 | 159,357 | 2.504 | 2.391 | 95,714 | 58 | 0 | 0 | 23 | 0 | 0.0 | n/a |
| agent (approve) | 55,541 | 158,012 | 2.845 | 2.634 | 102,471 | 39 | 3 | 0 | 0 | 0 | 0.0588 | 14.223 / 18.402 |
| agent_no_memory (approve) | 58,061 | 163,323 | 2.813 | 2.611 | 105,262 | 58 | 19 | 15 | 0 | 0 | 0.06 | 15.051 / 19.864 |
| agent (automate) | 57,670 | 161,759 | 2.805 | 2.611 | 104,089 | 34 | 3 | 0 | 0 | 0 | 0.0565 | 13.043 / 17.151 |

## Details

### hold

- proposals by status: {}
- rejections by rule: {}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 0, tool calls: 0, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 19606.08, "expected_true_revenue": 68586.51, "true_roas": 3.498}, "ridgeline": {"spend": 19612.9, "expected_true_revenue": 44862.89, "true_roas": 2.287}, "kindred": {"spend": 15720.29, "expected_true_revenue": 39084.08, "true_roas": 2.486}}

### roas_rule

- proposals by status: {'auto_approved': 52, 'blocked': 6}
- rejections by rule: {}
- guardrail interventions: {'brand_cap': 23}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 0, tool calls: 0, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 23430.69, "expected_true_revenue": 61601.87, "true_roas": 2.629}, "ridgeline": {"spend": 22135.53, "expected_true_revenue": 52966.77, "true_roas": 2.393}, "kindred": {"spend": 18076.34, "expected_true_revenue": 44788.07, "true_roas": 2.478}}

### agent (approve)

- proposals by status: {'rejected': 3, 'approved': 36}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1, 'below_target': 1}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 2; API retries: 0
- model calls: 73, tool calls: 115, tokens in/out: 298,338 / 57,962
- by brand: {"lumen": {"spend": 20071.94, "expected_true_revenue": 69158.25, "true_roas": 3.446}, "ridgeline": {"spend": 20413.48, "expected_true_revenue": 49374.16, "true_roas": 2.419}, "kindred": {"spend": 15055.33, "expected_true_revenue": 39479.19, "true_roas": 2.622}}

### agent_no_memory (approve)

- proposals by status: {'rejected': 19, 'approved': 39}
- rejections by rule: {'demand_capped': 7, 'strategic_prospecting': 8, 'below_target': 4}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 1; API retries: 0
- model calls: 72, tool calls: 127, tokens in/out: 287,970 / 62,492
- by brand: {"lumen": {"spend": 19628.29, "expected_true_revenue": 68825.25, "true_roas": 3.506}, "ridgeline": {"spend": 21266.34, "expected_true_revenue": 51126.7, "true_roas": 2.404}, "kindred": {"spend": 17166.43, "expected_true_revenue": 43370.89, "true_roas": 2.526}}

### agent (automate)

- proposals by status: {'rejected': 3, 'approved': 21, 'auto_approved': 10}
- rejections by rule: {'strategic_prospecting': 1, 'below_target': 1, 'demand_capped': 1}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 71, tool calls: 119, tokens in/out: 288,212 / 55,385
- by brand: {"lumen": {"spend": 20490.7, "expected_true_revenue": 69686.22, "true_roas": 3.401}, "ridgeline": {"spend": 20741.94, "expected_true_revenue": 50169.76, "true_roas": 2.419}, "kindred": {"spend": 16437.3, "expected_true_revenue": 41902.65, "true_roas": 2.549}}

