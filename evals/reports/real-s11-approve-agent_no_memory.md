# Eval report: real-s11-approve-agent_no_memory

- model: `claude-haiku-5-5`, store: `db`, seed: 11, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:31:44+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agent_no_memory | 157,247 | 452,139 | 2.875 | 2.592 | 294,891 | 66 | 22 | 17 | 0 | 35 | 0.0676 | 14.434 / 16.456 |

## Details

### agent_no_memory

- proposals by status: {'rejected': 22, 'approved': 44}
- rejections by rule: {'demand_capped': 9, 'strategic_prospecting': 10, 'below_target': 3}
- guardrail interventions: {}
- fallback reasons: {'model_error': 35}; output retries: 1; API retries: 0
- model calls: 86, tool calls: 146, tokens in/out: 338,460 / 67,556
- by brand: {"lumen": {"spend": 54572.07, "expected_true_revenue": 179515.67, "true_roas": 3.29}, "ridgeline": {"spend": 57559.77, "expected_true_revenue": 139547.85, "true_roas": 2.424}, "kindred": {"spend": 45115.56, "expected_true_revenue": 133075.14, "true_roas": 2.95}}

