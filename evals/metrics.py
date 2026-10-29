"""Scoring an ExperimentResult against hidden ground truth.

Headline metric: EXPECTED true revenue over the eval days, i.e. the noise-free value of
the response curve at the spend each policy actually chose, including the conversions
the platforms failed to report. Realized true revenue (with Poisson noise) and reported
revenue (what the agent saw) are reported next to it.

Rejected-proposal repetition: a rejection counts as a repeat when the reviewer had
already rejected the same campaign, in the same direction, for the same rule, on an
earlier day. That is the "told you no already" count memory should drive down.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from engine.simulation import ExperimentResult


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, round(q * (len(s) - 1)))]


def score(result: ExperimentResult, price_in: float, price_out: float) -> dict[str, Any]:
    warm = result.scenario.warmup_days
    rows = [t for t in result.truth if t.day >= warm]
    spend = sum(t.spend for t in rows)
    exp_rev = sum(t.expected_revenue for t in rows)
    true_rev = sum(t.true_revenue for t in rows)
    rep_rev = sum(t.reported_revenue for t in rows)
    by_brand = {}
    for b in result.scenario.brands:
        br = [t for t in rows if t.brand_id == b.brand_id]
        s, r = sum(t.spend for t in br), sum(t.expected_revenue for t in br)
        by_brand[b.brand_id] = {"spend": round(s, 2), "expected_true_revenue": round(r, 2),
                                "true_roas": round(r / s, 3) if s else None}

    proposals = [p for d in result.days for p in d.proposals]
    status = Counter(p.status for p in proposals)
    seen: set[tuple[str, str, str]] = set()
    repeats = 0
    rejections_by_rule: Counter[str] = Counter()
    for p in sorted(proposals, key=lambda p: (p.sim_day, p.proposal_id or 0)):
        if p.status != "rejected" or p.rule_id in (None, "execution_check"):
            continue
        rejections_by_rule[p.rule_id] += 1
        key = (p.campaign_id, p.direction, p.rule_id)
        if key in seen:
            repeats += 1
        seen.add(key)

    runs = [d.run for d in result.days]
    agent_runs = [r for r in runs if r.model_calls]
    tin = sum(r.input_tokens or 0 for r in runs)
    tout = sum(r.output_tokens or 0 for r in runs)
    lat = [r.latency_ms / 1000 for r in agent_runs]
    return {
        "experiment_id": result.experiment_id,
        "policy": result.policy,
        "model": result.model,
        "mode": result.mode,
        "memory": result.use_memory,
        "eval_days": result.scenario.eval_days,
        "brands": [b.brand_id for b in result.scenario.brands],
        "spend": round(spend, 2),
        "expected_true_revenue": round(exp_rev, 2),
        "realized_true_revenue": round(true_rev, 2),
        "reported_revenue": round(rep_rev, 2),
        "true_roas": round(exp_rev / spend, 3) if spend else None,
        "reported_roas": round(rep_rev / spend, 3) if spend else None,
        "net_after_ad_spend": round(exp_rev - spend, 2),
        "by_brand": by_brand,
        "proposals": len(proposals),
        "proposals_by_status": dict(status),
        "rejections": sum(rejections_by_rule.values()),
        "rejections_by_rule": dict(rejections_by_rule),
        "repeated_rejections": repeats,
        "guardrail_interventions": dict(Counter(g["rule"] for g in result.guardrail_events)),
        "runs": len(runs),
        "fallback_runs": sum(r.status == "fallback" for r in runs),
        "fallback_reasons": dict(Counter(r.fallback_reason for r in runs if r.fallback_reason)),
        "output_retries": sum(r.output_retries for r in runs),
        "api_retries": sum(r.api_retries for r in runs),
        "model_calls": sum(r.model_calls for r in runs),
        "tool_calls": sum(r.tool_calls for r in runs),
        "input_tokens": tin,
        "output_tokens": tout,
        "cost_usd": round(tin / 1e6 * price_in + tout / 1e6 * price_out, 4),
        "latency_s_mean": round(statistics.mean(lat), 2) if lat else None,
        "latency_s_p50": _pct(lat, 0.5),
        "latency_s_p95": _pct(lat, 0.95),
    }
