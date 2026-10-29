"""Re-score stored experiments over a shorter window, from Postgres alone.

Why this exists: on 2026-10-29 the API account ran out of credit partway through the
real-model runs. From then on every call failed and every run fell back to holding
budgets (as designed), so the 21-day totals mix agent days with forced-hold days. Each
simulated day depends only on earlier days, so the first N eval days of each experiment
are a valid N-day experiment on their own. This tool rebuilds them:

- budgets per day from the initial budgets plus `budget_changes` (Postgres),
- ground truth by re-running the deterministic market with the same seed on those
  budgets (one RNG per seed/campaign/day, so it reproduces the original run exactly),
- runs, proposals and guardrail events from Postgres, cut at the same day.

Check: re-scoring a complete experiment over its full length reproduces its report.

    uv run python -m evals.rescore --seed 7 --eval-days 9 --out NAME EXPERIMENT_ID ...
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta

from engine.cycle import DayRecord
from engine.simulation import ExperimentResult
from evals.metrics import score
from evals.run import REPORTS, render_markdown
from settings import get_settings
from sim.market import Market
from sim.scenario import default_scenario
from storage.state import PostgresStateStore


def rebuild(state: PostgresStateStore, experiment_id: str, seed: int,
            eval_days: int) -> ExperimentResult:
    scenario = default_scenario(eval_days=eval_days)
    market = Market(scenario, seed)
    last = market.date_of(scenario.warmup_days + eval_days - 1)
    runs = [r for r in state.list_runs(experiment_id) if r.sim_day <= last]
    if not runs:
        raise SystemExit(f"no runs for {experiment_id}")
    proposals = [p for p in state.list_proposals(experiment_id) if p.sim_day <= last]
    changes = state.conn.execute(
        "SELECT campaign_id, sim_day, new_budget FROM budget_changes WHERE experiment_id = %s "
        "ORDER BY change_id", (experiment_id,)).fetchall()
    budgets = {c.campaign_id: c.initial_budget for c in scenario.campaigns}
    result = ExperimentResult(experiment_id, runs[0].policy, runs[0].model, runs[0].mode,
                              use_memory=runs[0].policy == "agent", scenario=scenario)
    for day in range(scenario.warmup_days + eval_days):
        d = market.date_of(day)
        for cid, sim_day, new in changes:
            if sim_day == d:
                budgets[cid] = float(new)
        result.truth.extend(market.simulate_day(day, budgets).truth)
    by_run: dict[int, DayRecord] = {r.run_id: DayRecord(r) for r in runs}
    for p in proposals:
        by_run[p.run_id].proposals.append(p)
    result.days = list(by_run.values())
    result.guardrail_events = [g for g in state.list_guardrail_events(experiment_id)
                               if g["sim_day"] <= last]
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("experiments", nargs="+")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--eval-days", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    s = get_settings()
    state = PostgresStateStore.connect(s.database_url)
    scores = []
    for exp in args.experiments:
        sc = score(rebuild(state, exp, args.seed, args.eval_days), s.price_input_per_mtok,
                   s.price_output_per_mtok)
        sc["policy"] = f"{sc['policy']} ({sc['mode']})" if sc["model_calls"] else sc["policy"]
        scores.append(sc)
    start = Market(default_scenario()).date_of(7)
    meta = {"tag": args.out, "model": ", ".join(sorted({x["model"] for x in scores})),
            "store": "db (re-scored from Postgres)", "seed": args.seed, "mode": "see policy",
            "brands": scores[0]["brands"], "warmup_days": 7, "eval_days": args.eval_days,
            "generated_at": f"re-scored; eval window {start} to "
                            f"{start + timedelta(days=args.eval_days - 1)}",
            "sources": args.experiments,
            "total_model_spend_usd": round(sum(x["cost_usd"] for x in scores), 4)}
    (REPORTS / f"{args.out}.json").write_text(json.dumps({"meta": meta, "scores": scores},
                                                         indent=2, default=str))
    md = render_markdown(meta, scores)
    (REPORTS / f"{args.out}.md").write_text(md + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
