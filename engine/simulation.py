"""Run one policy over a whole simulated period.

    setup (Postgres: brands, campaigns at initial budgets; ClickHouse: clear experiment)
    for each day:
        if past warm-up: run_brand_day for every brand (budgets may change)
        market.simulate_day(today's budgets) -> events into ClickHouse, truth kept here

Ground truth never touches either database the agent reads from; it stays in the
returned ExperimentResult for the scorer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from agent.guardrails import GuardrailConfig
from approvals.reviewer import SimulatedReviewer
from engine.cycle import DayRecord, run_brand_day
from engine.policies import Policy
from sim.market import Market, TruthRow
from sim.scenario import Scenario
from storage.events import EventStore
from storage.models import Brand, Campaign
from storage.state import StateStore


@dataclass
class ExperimentResult:
    experiment_id: str
    policy: str
    model: str
    mode: str
    use_memory: bool
    scenario: Scenario
    truth: list[TruthRow] = field(default_factory=list)
    days: list[DayRecord] = field(default_factory=list)
    guardrail_events: list[dict] = field(default_factory=list)


def seed_state(state: StateStore, experiment_id: str, scenario: Scenario) -> None:
    state.setup_experiment(
        experiment_id,
        [Brand(b.brand_id, b.name, b.daily_budget_cap, b.min_learning_budget)
         for b in scenario.brands],
        [Campaign(c.campaign_id, c.brand_id, c.name, c.channel, c.objective, c.initial_budget)
         for c in scenario.campaigns])


def run_experiment(*, experiment_id: str, scenario: Scenario, policy: Policy,
                   state: StateStore, events: EventStore, mode: str = "approve",
                   use_memory: bool = True, reviewer_enabled: bool = True, seed: int = 7,
                   guard: GuardrailConfig | None = None,
                   on_day: Callable[[int, list[DayRecord]], None] | None = None
                   ) -> ExperimentResult:
    market = Market(scenario, seed)
    seed_state(state, experiment_id, scenario)
    events.reset(experiment_id)
    reviewer = SimulatedReviewer(scenario, events, experiment_id) if reviewer_enabled else None
    result = ExperimentResult(experiment_id, policy.name, policy.model, mode, use_memory,
                              scenario)
    for day in range(scenario.warmup_days + scenario.eval_days):
        today: list[DayRecord] = []
        if day >= scenario.warmup_days:
            for b in scenario.brands:
                today.append(run_brand_day(
                    experiment_id=experiment_id, sim_day=market.date_of(day),
                    brand_id=b.brand_id, policy=policy, state=state, events=events, mode=mode,
                    reviewer=reviewer, use_memory=use_memory, guard=guard))
        budgets = {c.campaign_id: c.daily_budget for c in state.list_campaigns(experiment_id)}
        outcome = market.simulate_day(day, budgets)
        events.insert_day(experiment_id, outcome)
        result.truth.extend(outcome.truth)
        result.days.extend(today)
        if on_day:
            on_day(day, today)
    result.guardrail_events = state.list_guardrail_events(experiment_id)
    return result
