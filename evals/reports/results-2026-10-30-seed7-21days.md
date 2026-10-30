# Eval report: results-2026-10-30-seed7-21days

- model: `claude-haiku-5-5 + scripted (RulePlayingModel, not an LLM)`, store: `db`, seed: 7, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:25:09+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hold | 144,249 | 412,781 | 2.862 | 2.535 | 268,531 | 0 | 0 | 0 | 0 | 0 | 0.0 | n/a |
| roas_rule | 172,745 | 423,252 | 2.45 | 2.3 | 250,507 | 134 | 0 | 0 | 89 | 0 | 0.0 | n/a |
| agent | 155,755 | 454,283 | 2.917 | 2.595 | 298,528 | 67 | 3 | 0 | 0 | 0 | 0.1577 | 13.823 / 21.629 |
| agent_no_memory | 158,132 | 451,864 | 2.858 | 2.542 | 293,732 | 114 | 49 | 44 | 0 | 0 | 0.1632 | 16.424 / 28.263 |
| agent | 151,896 | 445,006 | 2.93 | 2.62 | 293,109 | 56 | 3 | 0 | 1 | 1 | 0.1545 | 14.681 / 124.672 |

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

- proposals by status: {'rejected': 3, 'approved': 64}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1, 'below_target': 1}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 8; API retries: 0
- model calls: 182, tool calls: 306, tokens in/out: 799,612 / 155,471
- by brand: {"lumen": {"spend": 51080.59, "expected_true_revenue": 176243.1, "true_roas": 3.45}, "ridgeline": {"spend": 58639.83, "expected_true_revenue": 142011.88, "true_roas": 2.422}, "kindred": {"spend": 46034.85, "expected_true_revenue": 136028.51, "true_roas": 2.955}}

### agent_no_memory

- proposals by status: {'rejected': 49, 'approved': 65}
- rejections by rule: {'demand_capped': 19, 'strategic_prospecting': 21, 'below_target': 9}
- guardrail interventions: {}
- fallback reasons: {}; output retries: 6; API retries: 0
- model calls: 193, tool calls: 334, tokens in/out: 794,482 / 167,408
- by brand: {"lumen": {"spend": 55441.69, "expected_true_revenue": 178684.96, "true_roas": 3.223}, "ridgeline": {"spend": 57652.79, "expected_true_revenue": 139761.22, "true_roas": 2.424}, "kindred": {"spend": 45037.14, "expected_true_revenue": 133417.67, "true_roas": 2.962}}

### agent

- proposals by status: {'rejected': 3, 'approved': 34, 'auto_approved': 19}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1, 'below_target': 1}
- guardrail interventions: {'max_change': 1}
- fallback reasons: {'model_unavailable': 1}; output retries: 4; API retries: 21
- model calls: 184, tool calls: 304, tokens in/out: 784,845 / 152,069
- by brand: {"lumen": {"spend": 51445.75, "expected_true_revenue": 176480.42, "true_roas": 3.43}, "ridgeline": {"spend": 55289.23, "expected_true_revenue": 134945.51, "true_roas": 2.441}, "kindred": {"spend": 45161.16, "expected_true_revenue": 133579.61, "true_roas": 2.958}}

Total model spend: $0.4753
