"""Integration tests against the Docker Compose ClickHouse and Postgres.

    docker compose up -d --wait
    uv run pytest -m db
"""

from datetime import date

import pytest

from agent.scripted_model import RulePlayingModel
from engine.policies import AgentPolicy
from engine.simulation import run_experiment
from evals.metrics import score
from settings import get_settings
from sim.market import Market
from sim.scenario import default_scenario
from storage.events import ClickHouseEventStore, MemoryEventStore
from storage.models import Brand, Campaign, ProposalRecord, RunRecord
from storage.state import CapExceededError, MemoryStateStore, PostgresStateStore, StateError

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def ch():
    return ClickHouseEventStore.connect(get_settings())


@pytest.fixture(scope="module")
def pg():
    return PostgresStateStore.connect(get_settings().database_url)


def test_clickhouse_matches_memory_store(ch):
    s = default_scenario()
    m, mem = Market(s, seed=11), MemoryEventStore()
    ch.reset("it-events")
    budgets = {c.campaign_id: c.initial_budget for c in s.campaigns}
    for d in range(14):
        out = m.simulate_day(d, budgets)
        ch.insert_day("it-events", out)
        mem.insert_day("it-events", out)
    end = m.date_of(13)
    for brand in ("lumen", "ridgeline", "kindred"):
        for window in (1, 3, 7, 14):
            a = ch.window_metrics("it-events", brand, end, window)
            b = mem.window_metrics("it-events", brand, end, window)
            assert [x.campaign_id for x in a] == [x.campaign_id for x in b]
            for x, y in zip(a, b, strict=True):
                assert (x.days_with_data, x.impressions, x.clicks, x.conversions) == (
                    y.days_with_data, y.impressions, y.clicks, y.conversions)
                assert x.spend == pytest.approx(y.spend, abs=0.01)
                assert x.revenue == pytest.approx(y.revenue, abs=0.01)
    series = ch.daily_series("it-events", "ridge_tiktok_spark", end, 14)
    assert [p.conversions for p in series][12:] == [0, 0]  # tracking broke on day 12
    # the materialized-view rollup agrees with the raw event tables
    raw = ch.raw_daily_check("it-events", "ridge_tiktok_spark")
    assert [(r[1], r[2]) for r in raw] == [(p.clicks, p.conversions) for p in series]


def test_reset_removes_only_that_experiment(ch):
    s = default_scenario(brand_ids=["lumen"])
    m = Market(s)
    for exp in ("it-a", "it-b"):
        ch.reset(exp)
        ch.insert_day(exp, m.simulate_day(0, {c.campaign_id: 100 for c in s.campaigns}))
    ch.reset("it-a")
    assert ch.window_metrics("it-a", "lumen", m.date_of(0), 1) == []
    assert ch.window_metrics("it-b", "lumen", m.date_of(0), 1)


def test_postgres_decide_transaction_and_recall(pg):
    exp = "it-state"
    pg.setup_experiment(exp, [Brand("b1", "B", 1000, 50)],
                        [Campaign("c1", "b1", "C1", "meta", "prospecting", 400),
                         Campaign("c2", "b1", "C2", "google", "search", 500)])
    rid = pg.record_run(exp, RunRecord("b1", date(2026, 9, 8), "agent", "m", "approve"))

    def prop(cid, cur, final):
        p = ProposalRecord(rid, "b1", cid, date(2026, 9, 8), "increase", cur, final, final,
                           "reason text", "effect", "high", "pending", ["max_change"])
        pg.add_proposal(exp, p)
        return p

    a = prop("c1", 400, 480)
    assert pg.decide(exp, a.proposal_id, "approve", "rev", "ok").status == "approved"
    b = prop("c2", 500, 600)  # 480 + 600 > 1000 cap
    with pytest.raises(CapExceededError):
        pg.decide(exp, b.proposal_id, "approve", "rev", "ok")
    # the failed approval rolled back completely
    assert pg.get_proposal(exp, b.proposal_id).status == "pending"
    assert pg.recall(exp, "b1", date(2026, 9, 9))[0].campaign_id == "c1"
    pg.decide(exp, b.proposal_id, "reject", "rev", "over cap", "rule")
    with pytest.raises(StateError):
        pg.decide(exp, b.proposal_id, "approve", "rev", "again")
    got = pg.recall(exp, "b1", date(2026, 9, 9))
    assert [(m.campaign_id, m.decision) for m in got] == [("c2", "reject"), ("c1", "approve")]
    budgets = {c.campaign_id: c.daily_budget for c in pg.list_campaigns(exp)}
    assert budgets == {"c1": 480.0, "c2": 500.0}
    assert pg.list_proposals(exp, status="rejected")[0].decision_reason == "over cap"


def test_db_and_memory_experiments_score_identically(ch, pg):
    """Same scripted policy, same seed: ClickHouse + Postgres give the same result as Python."""
    scenario = default_scenario(eval_days=4)
    results = []
    for state, events in ((pg, ch), (MemoryStateStore(), MemoryEventStore())):
        r = run_experiment(experiment_id="it-e2e", scenario=scenario,
                           policy=AgentPolicy(RulePlayingModel(False), name="agent_no_memory"),
                           state=state, events=events, use_memory=False)
        s = score(r, 0.1, 0.5)
        s.pop("latency_s_mean"), s.pop("latency_s_p50"), s.pop("latency_s_p95")
        results.append(s)
    assert results[0] == results[1]
    assert results[0]["repeated_rejections"] > 0
