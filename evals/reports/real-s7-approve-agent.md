# Eval report: real-s7-approve-agent

- model: `claude-haiku-5-5`, store: `db`, seed: 7, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:31:44+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agent | 148,998 | 436,209 | 2.928 | 2.625 | 287,210 | 41 | 3 | 0 | 0 | 36 | 0.068 | 14.223 / 19.574 |

## Details

### agent

- proposals by status: {'rejected': 3, 'approved': 38}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1, 'below_target': 1}
- guardrail interventions: {}
- fallback reasons: {'model_error': 36}; output retries: 3; API retries: 0
- model calls: 84, tool calls: 132, tokens in/out: 347,117 / 66,610
- by brand: {"lumen": {"spend": 53962.59, "expected_true_revenue": 178758.96, "true_roas": 3.313}, "ridgeline": {"spend": 55148.75, "expected_true_revenue": 134919.69, "true_roas": 2.446}, "kindred": {"spend": 39887.07, "expected_true_revenue": 122530.08, "true_roas": 3.072}}

