"""Eval CLI: run policies over the simulated period and score them on ground truth.

    uv run python -m evals.run                                  # offline, scripted, in-memory
    uv run python -m evals.run --store db                       # same, on ClickHouse + Postgres
    uv run --env-file .env python -m evals.run --model anthropic --store db --budget-usd 4

Policies (comma-separated --policies):
    hold             keep every budget as is (baseline)
    roas_rule        +20% if 7-day ROAS >= 2.5, -20% if < 1.5 (baseline)
    agent            model proposes, simulated reviewer approves/rejects, memory on
    agent_no_memory  same, without reviewer memory in the prompt
Baselines execute their moves directly; every policy goes through the same guardrails.

--model scripted uses RulePlayingModel, a fixed rule played through the real tool loop
(see agent/scripted_model.py). It tests the pipeline, not Claude.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.loop import LoopConfig
from agent.model_client import ModelTurn
from engine.policies import AgentPolicy, HoldPolicy, RoasRulePolicy
from engine.simulation import run_experiment
from evals.metrics import score
from settings import ROOT, get_settings
from sim.scenario import default_scenario

REPORTS = ROOT / "evals" / "reports"


class BudgetExceeded(Exception):
    """Raised before a model call that would start after the spend budget is used up."""


class BudgetGuard:
    """Wraps a model and stops the whole eval once spend reaches the budget."""

    def __init__(self, inner: Any, budget_usd: float, price_in: float, price_out: float):
        self.inner, self.budget = inner, budget_usd
        self.price_in, self.price_out = price_in, price_out
        self.name = inner.name
        self.spent = 0.0

    def complete(self, **kwargs: Any) -> ModelTurn:
        if self.spent >= self.budget:
            raise BudgetExceeded(f"spent ${self.spent:.4f} of ${self.budget:.2f}")
        turn = self.inner.complete(**kwargs)
        self.spent += ((turn.input_tokens or 0) * self.price_in
                       + (turn.output_tokens or 0) * self.price_out) / 1e6
        return turn


def make_model(kind: str, reads_memory: bool, guard: BudgetGuard | None) -> Any:
    if kind == "scripted":
        from agent.scripted_model import RulePlayingModel

        return RulePlayingModel(reads_memory=reads_memory)
    assert guard is not None
    return guard


def make_stores(kind: str) -> tuple[Any, Any]:
    if kind == "memory":
        from storage.events import MemoryEventStore
        from storage.state import MemoryStateStore

        return MemoryStateStore(), MemoryEventStore()
    from storage.events import ClickHouseEventStore
    from storage.state import PostgresStateStore

    s = get_settings()
    return PostgresStateStore.connect(s.database_url), ClickHouseEventStore.connect(s)


def render_markdown(meta: dict[str, Any], scores: list[dict[str, Any]]) -> str:
    lines = [f"# Eval report: {meta['tag']}", "",
             f"- model: `{meta['model']}`, store: `{meta['store']}`, seed: {meta['seed']}, "
             f"mode: `{meta['mode']}`",
             f"- brands: {', '.join(meta['brands'])}; warm-up {meta['warmup_days']} days, "
             f"eval {meta['eval_days']} days",
             f"- generated: {meta['generated_at']}", "",
             "| policy | spend | expected true revenue | true ROAS | reported ROAS | "
             "net after ad spend | proposals | rejected | repeated rejections | "
             "guardrail interventions | fallbacks | cost (USD) | latency p50 / p95 (s) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in scores:
        gi = sum(s["guardrail_interventions"].values())
        lat = (f"{s['latency_s_p50']} / {s['latency_s_p95']}" if s["latency_s_p50"] is not None
               else "n/a")
        lines.append(
            f"| {s['policy']} | {s['spend']:,.0f} | {s['expected_true_revenue']:,.0f} | "
            f"{s['true_roas']} | {s['reported_roas']} | {s['net_after_ad_spend']:,.0f} | "
            f"{s['proposals']} | {s['rejections']} | {s['repeated_rejections']} | {gi} | "
            f"{s['fallback_runs']} | {s['cost_usd']} | {lat} |")
    lines += ["", "## Details", ""]
    for s in scores:
        lines += [f"### {s['policy']}", "",
                  f"- proposals by status: {s['proposals_by_status']}",
                  f"- rejections by rule: {s['rejections_by_rule']}",
                  f"- guardrail interventions: {s['guardrail_interventions']}",
                  f"- fallback reasons: {s['fallback_reasons']}; output retries: "
                  f"{s['output_retries']}; API retries: {s['api_retries']}",
                  f"- model calls: {s['model_calls']}, tool calls: {s['tool_calls']}, tokens "
                  f"in/out: {s['input_tokens']:,} / {s['output_tokens']:,}",
                  f"- by brand: {json.dumps(s['by_brand'])}", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=["scripted", "anthropic"], default="scripted")
    ap.add_argument("--store", choices=["memory", "db"], default="memory")
    ap.add_argument("--policies", default="hold,roas_rule,agent,agent_no_memory")
    ap.add_argument("--mode", choices=["suggest", "approve", "automate"], default="approve")
    ap.add_argument("--days", type=int, default=21, help="eval days after the 7-day warm-up")
    ap.add_argument("--brands", default="", help="comma-separated brand ids (default: all)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--budget-usd", type=float, default=4.0,
                    help="hard stop for model spend across the whole run")
    ap.add_argument("--tag", default="")
    args = ap.parse_args(argv)

    settings = get_settings()
    scenario = default_scenario(eval_days=args.days,
                                brand_ids=[b for b in args.brands.split(",") if b] or None)
    tag = args.tag or f"{args.model}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    state, events = make_stores(args.store)
    guard = None
    if args.model == "anthropic":
        from agent.anthropic_model import AnthropicModel

        inner = AnthropicModel(settings.agent_model, effort=settings.agent_effort,
                               max_tokens=settings.model_max_tokens,
                               timeout_s=settings.model_timeout_s)
        guard = BudgetGuard(inner, args.budget_usd, settings.price_input_per_mtok,
                            settings.price_output_per_mtok)
    loop_cfg = LoopConfig(max_tool_steps=settings.max_tool_steps,
                          max_model_attempts=settings.model_max_attempts)

    scores = []
    for name in [p.strip() for p in args.policies.split(",") if p.strip()]:
        if name == "hold":
            policy, use_memory = HoldPolicy(), False
        elif name == "roas_rule":
            policy, use_memory = RoasRulePolicy(), False
        elif name in ("agent", "agent_no_memory"):
            use_memory = name == "agent"
            policy = AgentPolicy(make_model(args.model, use_memory, guard), loop_cfg, name=name)
        else:
            ap.error(f"unknown policy {name}")

        def progress(day: int, records: list, _name: str = name) -> None:
            if records:
                ok = sum(r.run.status == "ok" for r in records)
                spent = f" spent=${guard.spent:.4f}" if guard else ""
                print(f"[{_name}] day {day}: {ok}/{len(records)} runs ok{spent}",
                      file=sys.stderr, flush=True)

        try:
            result = run_experiment(experiment_id=f"{tag}-{name}", scenario=scenario,
                                    policy=policy, state=state, events=events, mode=args.mode,
                                    use_memory=use_memory, seed=args.seed, on_day=progress)
        except BudgetExceeded as exc:
            print(f"stopped: budget reached during {name} ({exc})", file=sys.stderr)
            break
        scores.append(score(result, settings.price_input_per_mtok,
                            settings.price_output_per_mtok))

    meta = {"tag": tag, "model": settings.agent_model if args.model == "anthropic"
            else "scripted (RulePlayingModel, not an LLM)", "store": args.store,
            "seed": args.seed, "mode": args.mode, "brands": [b.brand_id for b in scenario.brands],
            "warmup_days": scenario.warmup_days, "eval_days": scenario.eval_days,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "total_model_spend_usd": round(guard.spent, 4) if guard else 0.0}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{tag}.json").write_text(json.dumps({"meta": meta, "scores": scores}, indent=2))
    md = render_markdown(meta, scores)
    (REPORTS / f"{tag}.md").write_text(md + "\n")
    print(md)
    print(f"\nreports: {Path('evals/reports') / tag}.json / .md", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
