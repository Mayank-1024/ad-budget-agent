> **Do not use these totals as a score.** The API account ran out of credit on 2026-10-29 partway through these runs; from simulated day 2026-09-16/17 every agent run fell back to holding budgets. See `results-2026-10-29-seed11-8days.md` for the clean 8-day window.

# Eval report: results-2026-10-29-seed11

- model: `claude-haiku-5-5 + scripted (RulePlayingModel, not an LLM)`, store: `db`, seed: 11, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T10:25:14+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hold | 143,966 | 411,904 | 2.861 | 2.512 | 267,938 | 0 | 0 | 0 | 0 | 0 | 0.0 | n/a |
| roas_rule | 171,885 | 427,691 | 2.488 | 2.329 | 255,806 | 128 | 0 | 0 | 76 | 0 | 0.0 | n/a |
| agent | 150,415 | 444,194 | 2.953 | 2.665 | 293,779 | 35 | 3 | 0 | 0 | 35 | 0.0689 | 14.401 / 18.791 |
| agent_no_memory | 157,247 | 452,139 | 2.875 | 2.592 | 294,891 | 66 | 22 | 17 | 0 | 35 | 0.0676 | 14.434 / 16.456 |

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

### agent

- proposals by status: {'rejected': 3, 'approved': 32}
- rejections by rule: {'demand_capped': 1, 'strategic_prospecting': 1, 'below_target': 1}
- guardrail interventions: {}
- fallback reasons: {'model_error': 35}; output retries: 1; API retries: 0
- model calls: 83, tool calls: 138, tokens in/out: 340,996 / 69,690
- by brand: {"lumen": {"spend": 49842.5, "expected_true_revenue": 175139.02, "true_roas": 3.514}, "ridgeline": {"spend": 54679.78, "expected_true_revenue": 133554.92, "true_roas": 2.442}, "kindred": {"spend": 45893.07, "expected_true_revenue": 135500.39, "true_roas": 2.953}}

### agent_no_memory

- proposals by status: {'rejected': 22, 'approved': 44}
- rejections by rule: {'demand_capped': 9, 'strategic_prospecting': 10, 'below_target': 3}
- guardrail interventions: {}
- fallback reasons: {'model_error': 35}; output retries: 1; API retries: 0
- model calls: 86, tool calls: 146, tokens in/out: 338,460 / 67,556
- by brand: {"lumen": {"spend": 54572.07, "expected_true_revenue": 179515.67, "true_roas": 3.29}, "ridgeline": {"spend": 57559.77, "expected_true_revenue": 139547.85, "true_roas": 2.424}, "kindred": {"spend": 45115.56, "expected_true_revenue": 133075.14, "true_roas": 2.95}}

Total model spend: $0.1365
