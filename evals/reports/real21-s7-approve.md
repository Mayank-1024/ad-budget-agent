# Eval report: real21-s7-approve

- model: `claude-haiku-5-5`, store: `db`, seed: 7, mode: `approve`
- brands: lumen, ridgeline, kindred; warm-up 7 days, eval 21 days
- generated: 2026-10-29T13:56:00+00:00

| policy | spend | expected true revenue | true ROAS | reported ROAS | net after ad spend | proposals | rejected | repeated rejections | guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agent | 155,755 | 454,283 | 2.917 | 2.595 | 298,528 | 67 | 3 | 0 | 0 | 0 | 0.1577 | 13.823 / 21.629 |
| agent_no_memory | 158,132 | 451,864 | 2.858 | 2.542 | 293,732 | 114 | 49 | 44 | 0 | 0 | 0.1632 | 16.424 / 28.263 |

## Details

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

