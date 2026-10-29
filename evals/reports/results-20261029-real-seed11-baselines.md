# Eval report: results-20261029-real-seed11-baselines

- model: `scripted (RulePlayingModel, not an LLM)`, store: `db`, seed: 11, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:22:20+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hold | 143,966 | 411,904 | 2.861 | 2.512 | 267,938 | 0 | 0 | 0 | 0 | 0 | 0.0 | n/a |
| roas_rule | 171,885 | 427,691 | 2.488 | 2.329 | 255,806 | 128 | 0 | 0 | 76 | 0 | 0.0 | n/a |

## Details

### hold

- proposals by status: {}
- rejections by rule: {}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 0, tool calls: 0, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 51505.3, "expected_true_revenue": 175123.89, "true_roas": 3.4}, "ridgeline": {"spend": 51359.44, "expected_true_revenue": 117503.94, "true_roas": 2.288}, "kindred": {"spend": 41101.29, "expected_true_revenue": 119275.95, "true_roas": 2.902}}

### roas_rule

- proposals by status: {'auto_approved': 81, 'blocked': 47}
- rejections by rule: {}
- guardrail interventions: {'brand_cap': 60, 'tracking_freeze': 13, 'min_learning': 3}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 0, tool calls: 0, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 65936.6, "expected_true_revenue": 148522.87, "true_roas": 2.253}, "ridgeline": {"spend": 58926.41, "expected_true_revenue": 141485.91, "true_roas": 2.401}, "kindred": {"spend": 47021.6, "expected_true_revenue": 137681.98, "true_roas": 2.928}}

