# Eval report: real21-s11-approve

- model: `claude-haiku-5-5`, store: `db`, seed: 11, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T16:59:49+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agent | 155,686 | 451,567 | 2.9 | 2.589 | 295,881 | 61 | 2 | 0 | 0 | 0 | 0.1499 | 14.5 / 19.509 |
| agent_no_memory | 159,679 | 456,401 | 2.858 | 2.585 | 296,722 | 115 | 47 | 41 | 1 | 1 | 0.1546 | 14.732 / 38.426 |

## Details

### agent

- proposals by status: {'rejected': 2, 'approved': 59}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 4; API retries: 1
- model calls: 186, tool calls: 301, tokens in/out: 767,948 / 146,303
- by brand: {"lumen": {"spend": 52043.12, "expected_true_revenue": 177489.06, "true_roas": 3.41}, "ridgeline": {"spend": 57150.69, "expected_true_revenue": 137645.8, "true_roas": 2.408}, "kindred": {"spend": 46492.43, "expected_true_revenue": 136432.62, "true_roas": 2.935}}

### agent_no_memory

- proposals by status: {'rejected': 47, 'approved': 68}
- rejections by rule: {'demand_capped': 19, 'strategic_prospecting': 21, 'below_target': 7}
- guardrail interventions: {'max_change': 1}
- fallback reasons: {'invalid_output': 1}; output retries: 3; API retries: 5
- model calls: 191, tool calls: 328, tokens in/out: 769,379 / 155,349
- by brand: {"lumen": {"spend": 55698.09, "expected_true_revenue": 180015.26, "true_roas": 3.232}, "ridgeline": {"spend": 57830.14, "expected_true_revenue": 140144.75, "true_roas": 2.423}, "kindred": {"spend": 46150.75, "expected_true_revenue": 136240.9, "true_roas": 2.952}}

