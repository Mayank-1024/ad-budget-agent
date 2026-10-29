# Eval report: real-s7-automate-agent

- model: `claude-haiku-5-5`, store: `db`, seed: 7, mode: `automate`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:31:43+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agent | 157,760 | 452,649 | 2.869 | 2.561 | 294,889 | 38 | 3 | 0 | 0 | 35 | 0.0677 | 13.267 / 17.561 |

## Details

### agent

- proposals by status: {'rejected': 3, 'approved': 24, 'auto_approved': 11}
- rejections by rule: {'strategic_prospecting': 1, 'below_target': 1, 'demand_capped': 1}
- guardrail interventions: {}
- fallback reasons: {'model_error': 35}; output retries: 0; API retries: 0
- model calls: 85, tool calls: 145, tokens in/out: 344,900 / 66,515
- by brand: {"lumen": {"spend": 54989.49, "expected_true_revenue": 179453.89, "true_roas": 3.263}, "ridgeline": {"spend": 57085.71, "expected_true_revenue": 138609.55, "true_roas": 2.428}, "kindred": {"spend": 45684.56, "expected_true_revenue": 134585.08, "true_roas": 2.946}}

