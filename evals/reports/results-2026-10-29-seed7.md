> **Do not use these totals as a score.** The API account ran out of credit on 2026-10-29 partway through these runs; from simulated day 2026-09-16/17 every agent run fell back to holding budgets. See `results-2026-10-29-seed7-8days.md` for the clean 8-day window.

# Eval report: results-2026-10-29-seed7

- model: `claude-haiku-5-5 + scripted (RulePlayingModel, not an LLM)`, store: `db`, seed: 7, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:25:09+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hold | 144,249 | 412,781 | 2.862 | 2.535 | 268,531 | 0 | 0 | 0 | 0 | 0 | 0.0 | n/a |
| roas_rule | 172,745 | 423,252 | 2.45 | 2.3 | 250,507 | 134 | 0 | 0 | 89 | 0 | 0.0 | n/a |
| agent | 148,998 | 436,209 | 2.928 | 2.625 | 287,210 | 41 | 3 | 0 | 0 | 36 | 0.068 | 14.223 / 19.574 |
| agent_no_memory | 154,438 | 450,299 | 2.916 | 2.619 | 295,862 | 60 | 21 | 17 | 0 | 38 | 0.0656 | 14.465 / 19.864 |
| agent | 157,760 | 452,649 | 2.869 | 2.561 | 294,889 | 38 | 3 | 0 | 0 | 35 | 0.0677 | 13.267 / 17.561 |

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

- proposals by status: {'rejected': 3, 'approved': 38}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1, 'below_target': 1}
- guardrail interventions: {}
- fallback reasons: {'model_error': 36}; output retries: 3; API retries: 0
- model calls: 84, tool calls: 132, tokens in/out: 347,117 / 66,610
- by brand: {"lumen": {"spend": 53962.59, "expected_true_revenue": 178758.96, "true_roas": 3.313}, "ridgeline": {"spend": 55148.75, "expected_true_revenue": 134919.69, "true_roas": 2.446}, "kindred": {"spend": 39887.07, "expected_true_revenue": 122530.08, "true_roas": 3.072}}

### agent_no_memory

- proposals by status: {'rejected': 21, 'approved': 39}
- rejections by rule: {'demand_capped': 8, 'strategic_prospecting': 9, 'below_target': 4}
- guardrail interventions: {}
- fallback reasons: {'model_error': 38}; output retries: 2; API retries: 0
- model calls: 78, tool calls: 139, tokens in/out: 314,910 / 68,210
- by brand: {"lumen": {"spend": 51694.55, "expected_true_revenue": 176939.79, "true_roas": 3.423}, "ridgeline": {"spend": 58244.97, "expected_true_revenue": 140931.67, "true_roas": 2.42}, "kindred": {"spend": 44498.22, "expected_true_revenue": 132427.99, "true_roas": 2.976}}

### agent

- proposals by status: {'rejected': 3, 'approved': 24, 'auto_approved': 11}
- rejections by rule: {'strategic_prospecting': 1, 'below_target': 1, 'demand_capped': 1}
- guardrail interventions: {}
- fallback reasons: {'model_error': 35}; output retries: 0; API retries: 0
- model calls: 85, tool calls: 145, tokens in/out: 344,900 / 66,515
- by brand: {"lumen": {"spend": 54989.49, "expected_true_revenue": 179453.89, "true_roas": 3.263}, "ridgeline": {"spend": 57085.71, "expected_true_revenue": 138609.55, "true_roas": 2.428}, "kindred": {"spend": 45684.56, "expected_true_revenue": 134585.08, "true_roas": 2.946}}

Total model spend: $0.2013
