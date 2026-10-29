# Eval report: results-2026-10-29-seed11-8days

- model: `claude-haiku-5-5, none`, store: `db (re-scored from Postgres)`, seed: 11, mode: `see policy`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 8 days
- generated: re-scored; eval window 2026-09-08 to 2026-09-15

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hold | 54,849 | 152,284 | 2.776 | 2.489 | 97,435 | 0 | 0 | 0 | 0 | 0 | 0.0 | n/a |
| roas_rule | 63,837 | 160,558 | 2.515 | 2.348 | 96,720 | 54 | 0 | 0 | 18 | 0 | 0.0 | n/a |
| agent (approve) | 56,736 | 160,556 | 2.83 | 2.594 | 103,820 | 32 | 3 | 0 | 0 | 0 | 0.0575 | 14.389 / 16.581 |
| agent_no_memory (approve) | 58,230 | 163,284 | 2.804 | 2.552 | 105,054 | 55 | 18 | 13 | 0 | 0 | 0.0584 | 14.434 / 16.456 |

## Details

### hold

- proposals by status: {}
- rejections by rule: {}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 0, tool calls: 0, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 19669.21, "expected_true_revenue": 68678.33, "true_roas": 3.492}, "ridgeline": {"spend": 19522.72, "expected_true_revenue": 44647.43, "true_roas": 2.287}, "kindred": {"spend": 15656.8, "expected_true_revenue": 38957.88, "true_roas": 2.488}}

### roas_rule

- proposals by status: {'auto_approved': 51, 'blocked': 3}
- rejections by rule: {}
- guardrail interventions: {'brand_cap': 18}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 0, tool calls: 0, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 24058.4, "expected_true_revenue": 63417.28, "true_roas": 2.636}, "ridgeline": {"spend": 21992.26, "expected_true_revenue": 52680.51, "true_roas": 2.395}, "kindred": {"spend": 17786.58, "expected_true_revenue": 44459.88, "true_roas": 2.5}}

### agent (approve)

- proposals by status: {'rejected': 3, 'approved': 29}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1, 'below_target': 1}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 70, tool calls: 119, tokens in/out: 283,371 / 58,356
- by brand: {"lumen": {"spend": 19668.15, "expected_true_revenue": 68927.77, "true_roas": 3.505}, "ridgeline": {"spend": 20368.35, "expected_true_revenue": 49212.4, "true_roas": 2.416}, "kindred": {"spend": 16699.03, "expected_true_revenue": 42415.46, "true_roas": 2.54}}

### agent_no_memory (approve)

- proposals by status: {'rejected': 18, 'approved': 37}
- rejections by rule: {'demand_capped': 7, 'strategic_prospecting': 8, 'below_target': 3}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 1; API retries: 0
- model calls: 74, tool calls: 127, tokens in/out: 294,444 / 57,884
- by brand: {"lumen": {"spend": 20285.16, "expected_true_revenue": 69761.89, "true_roas": 3.439}, "ridgeline": {"spend": 20632.07, "expected_true_revenue": 50020.77, "true_roas": 2.424}, "kindred": {"spend": 17312.82, "expected_true_revenue": 43501.73, "true_roas": 2.513}}

