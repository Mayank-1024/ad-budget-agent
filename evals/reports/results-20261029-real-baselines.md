# Eval report: results-20261029-real-baselines

- model: `scripted (RulePlayingModel, not an LLM)`, store: `db`, seed: 7, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:17:56+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hold | 144,249 | 412,781 | 2.862 | 2.535 | 268,531 | 0 | 0 | 0 | 0 | 0 | 0.0 | n/a |
| roas_rule | 172,745 | 423,252 | 2.45 | 2.3 | 250,507 | 134 | 0 | 0 | 89 | 0 | 0.0 | n/a |

## Details

### hold

- proposals by status: {}
- rejections by rule: {}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 0, tool calls: 0, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 51492.91, "expected_true_revenue": 175214.36, "true_roas": 3.403}, "ridgeline": {"spend": 51494.23, "expected_true_revenue": 117845.53, "true_roas": 2.289}, "kindred": {"spend": 41262.17, "expected_true_revenue": 119720.83, "true_roas": 2.901}}

### roas_rule

- proposals by status: {'auto_approved': 70, 'blocked': 64}
- rejections by rule: {}
- guardrail interventions: {'brand_cap': 65, 'tracking_freeze': 13, 'min_learning': 11}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 0, tool calls: 0, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 66105.94, "expected_true_revenue": 143116.34, "true_roas": 2.165}, "ridgeline": {"spend": 59164.98, "expected_true_revenue": 141844.2, "true_roas": 2.397}, "kindred": {"spend": 47474.1, "expected_true_revenue": 138291.47, "true_roas": 2.913}}

