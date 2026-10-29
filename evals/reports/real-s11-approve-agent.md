# Eval report: real-s11-approve-agent

- model: `claude-haiku-5-5`, store: `db`, seed: 11, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:31:46+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agent | 150,415 | 444,194 | 2.953 | 2.665 | 293,779 | 35 | 3 | 0 | 0 | 35 | 0.0689 | 14.401 / 18.791 |

## Details

### agent

- proposals by status: {'rejected': 3, 'approved': 32}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1, 'below_target': 1}
- guardrail interventions: {}
- fallback reasons: {'model_error': 35}; output retries: 1; API retries: 0
- model calls: 83, tool calls: 138, tokens in/out: 340,996 / 69,690
- by brand: {"lumen": {"spend": 49842.5, "expected_true_revenue": 175139.02, "true_roas": 3.514}, "ridgeline": {"spend": 54679.78, "expected_true_revenue": 133554.92, "true_roas": 2.442}, "kindred": {"spend": 45893.07, "expected_true_revenue": 135500.39, "true_roas": 2.953}}

