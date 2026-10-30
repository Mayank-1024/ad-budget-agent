# Eval report: real21-s7-automate

- model: `claude-haiku-5-5`, store: `db`, seed: 7, mode: `automate`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-30T05:32:58+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agent | 151,896 | 445,006 | 2.93 | 2.62 | 293,109 | 56 | 3 | 0 | 1 | 1 | 0.1545 | 14.681 / 124.672 |

## Details

### agent

- proposals by status: {'rejected': 3, 'approved': 34, 'auto_approved': 19}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1, 'below_target': 1}
- guardrail interventions: {'max_change': 1}
- fallback reasons: {'model_unavailable': 1}; output retries: 4; API retries: 21
- model calls: 184, tool calls: 304, tokens in/out: 784,845 / 152,069
- by brand: {"lumen": {"spend": 51445.75, "expected_true_revenue": 176480.42, "true_roas": 3.43}, "ridgeline": {"spend": 55289.23, "expected_true_revenue": 134945.51, "true_roas": 2.441}, "kindred": {"spend": 45161.16, "expected_true_revenue": 133579.61, "true_roas": 2.958}}

