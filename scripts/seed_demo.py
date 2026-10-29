"""Seed a demo experiment for the dashboard: history with reviewer decisions, then one
day of proposals left pending for a person to approve or reject.

    docker compose up -d --wait
    uv run python -m scripts.seed_demo                      # scripted proposals (offline)
    uv run --env-file .env python -m scripts.seed_demo --model anthropic   # Claude proposals
"""

from __future__ import annotations

import argparse

from agent.loop import LoopConfig
from engine.cycle import run_brand_day
from engine.policies import AgentPolicy
from engine.simulation import run_experiment
from settings import get_settings
from sim.market import Market
from sim.scenario import default_scenario
from storage.events import ClickHouseEventStore
from storage.state import PostgresStateStore


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["scripted", "anthropic"], default="scripted")
    ap.add_argument("--days", type=int, default=6, help="reviewed days before the open day")
    ap.add_argument("--experiment", default="demo")
    args = ap.parse_args(argv)
    s = get_settings()
    state, events = PostgresStateStore.connect(s.database_url), ClickHouseEventStore.connect(s)
    if args.model == "anthropic":
        from agent.anthropic_model import AnthropicModel

        model = AnthropicModel(s.agent_model, effort=s.agent_effort)
    else:
        from agent.scripted_model import RulePlayingModel

        model = RulePlayingModel()
    policy = AgentPolicy(model, LoopConfig(max_tool_steps=s.max_tool_steps))
    scenario = default_scenario(eval_days=args.days)
    run_experiment(experiment_id=args.experiment, scenario=scenario, policy=policy,
                   state=state, events=events, mode="approve")
    open_day = Market(scenario).date_of(scenario.warmup_days + scenario.eval_days)
    for b in scenario.brands:
        run_brand_day(experiment_id=args.experiment, sim_day=open_day, brand_id=b.brand_id,
                      policy=policy, state=state, events=events, mode="approve",
                      reviewer=None, use_memory=True)
    pending = state.list_proposals(args.experiment, status="pending")
    print(f"experiment {args.experiment!r}: {len(pending)} proposals pending for {open_day}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
