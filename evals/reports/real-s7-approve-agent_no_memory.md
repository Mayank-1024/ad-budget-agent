# Eval report: real-s7-approve-agent_no_memory

- model: `claude-haiku-5-5`, store: `db`, seed: 7, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:31:45+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agent_no_memory | 154,438 | 450,299 | 2.916 | 2.619 | 295,862 | 60 | 21 | 17 | 0 | 38 | 0.0656 | 14.465 / 19.864 |

## Details

### agent_no_memory

- proposals by status: {'rejected': 21, 'approved': 39}
- rejections by rule: {'demand_capped': 8, 'strategic_prospecting': 9, 'below_target': 4}
- guardrail interventions: {}
- fallback reasons: {'model_error': 38}; output retries: 2; API retries: 0
- model calls: 78, tool calls: 139, tokens in/out: 314,910 / 68,210
- by brand: {"lumen": {"spend": 51694.55, "expected_true_revenue": 176939.79, "true_roas": 3.423}, "ridgeline": {"spend": 58244.97, "expected_true_revenue": 140931.67, "true_roas": 2.42}, "kindred": {"spend": 44498.22, "expected_true_revenue": 132427.99, "true_roas": 2.976}}

