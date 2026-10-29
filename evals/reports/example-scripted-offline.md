# Eval report: example-scripted-offline

- model: `scripted (RulePlayingModel, not an LLM)`, store: `memory`, seed: 7, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:25:14+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hold | 144,249 | 412,781 | 2.862 | 2.535 | 268,531 | 0 | 0 | 0 | 0 | 0 | 0.0 | n/a |
| roas_rule | 172,745 | 423,252 | 2.45 | 2.3 | 250,507 | 134 | 0 | 0 | 89 | 0 | 0.0 | n/a |
| agent | 168,732 | 459,254 | 2.722 | 2.414 | 290,522 | 112 | 2 | 0 | 60 | 0 | 0.0 | 0.0 / 0.0 |
| agent_no_memory | 168,732 | 459,254 | 2.722 | 2.414 | 290,522 | 152 | 42 | 40 | 60 | 0 | 0.0 | 0.0 / 0.0 |

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

### agent

- proposals by status: {'rejected': 2, 'approved': 74, 'blocked': 36}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1}
- guardrail interventions: {'brand_cap': 60}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 126, tool calls: 126, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 62368.04, "expected_true_revenue": 180032.29, "true_roas": 2.887}, "ridgeline": {"spend": 58948.57, "expected_true_revenue": 141217.59, "true_roas": 2.396}, "kindred": {"spend": 47415.08, "expected_true_revenue": 138003.96, "true_roas": 2.911}}

### agent_no_memory

- proposals by status: {'rejected': 42, 'approved': 74, 'blocked': 36}
- rejections by rule: {'demand_capped': 21, 'strategic_prospecting': 21}
- guardrail interventions: {'brand_cap': 60}
- fallback reasons: {}; output retries: 0; API retries: 0
- model calls: 126, tool calls: 126, tokens in/out: 0 / 0
- by brand: {"lumen": {"spend": 62368.04, "expected_true_revenue": 180032.29, "true_roas": 2.887}, "ridgeline": {"spend": 58948.57, "expected_true_revenue": 141217.59, "true_roas": 2.396}, "kindred": {"spend": 47415.08, "expected_true_revenue": 138003.96, "true_roas": 2.911}}

