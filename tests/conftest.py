from __future__ import annotations

from datetime import date

import pytest

from agent.tools import DayContext
from engine.simulation import seed_state
from sim.market import Market
from sim.scenario import default_scenario
from storage.events import MemoryEventStore
from storage.models import Brand, Campaign
from storage.state import MemoryStateStore

EXP = "test"


@pytest.fixture
def scenario():
    return default_scenario(eval_days=5)


@pytest.fixture
def brand():
    return Brand("b1", "Brand One", daily_budget_cap=1000, min_learning_budget=50)


@pytest.fixture
def campaigns():
    return [Campaign("c1", "b1", "C1", "meta", "prospecting", 400),
            Campaign("c2", "b1", "C2", "google", "search", 300),
            Campaign("c3", "b1", "C3", "tiktok", "prospecting", 200)]


@pytest.fixture
def seeded(scenario):
    """State + events with 7 warm-up days of data for the default scenario."""
    state, events = MemoryStateStore(), MemoryEventStore()
    seed_state(state, EXP, scenario)
    market = Market(scenario, seed=7)
    budgets = {c.campaign_id: c.initial_budget for c in scenario.campaigns}
    for d in range(scenario.warmup_days):
        events.insert_day(EXP, market.simulate_day(d, budgets))
    return state, events, market


@pytest.fixture
def lumen_ctx(seeded):
    state, events, market = seeded
    return DayContext(EXP, state.get_brand(EXP, "lumen"), state.list_campaigns(EXP, "lumen"),
                      market.date_of(7), events)


def day(n: int) -> date:
    return date(2026, 9, 1 + n)
