from datetime import date

from sim.market import Market
from sim.scenario import default_scenario
from storage.events import CampaignWindow, MemoryEventStore, window_bounds


def test_window_bounds_inclusive():
    assert window_bounds(date(2026, 9, 7), 7) == (date(2026, 9, 1), date(2026, 9, 7))
    assert window_bounds(date(2026, 9, 7), 1) == (date(2026, 9, 7), date(2026, 9, 7))


def test_ratios_from_sums_not_averages():
    w = CampaignWindow("c", 2, spend=300.0, impressions=10000, clicks=200, conversions=0,
                       revenue=0.0)
    assert w.roas == 0.0 and w.cpa is None and w.ctr == 0.02 and w.cvr == 0.0
    assert CampaignWindow("c", 0, 0.0, 0, 0, 0, 0.0).roas is None


def test_memory_store_aggregates_events():
    s = default_scenario()
    m, store = Market(s), MemoryEventStore()
    budgets = {c.campaign_id: c.initial_budget for c in s.campaigns}
    outs = [m.simulate_day(d, budgets) for d in range(3)]
    for o in outs:
        store.insert_day("e", o)
    rows = {w.campaign_id: w for w in store.window_metrics("e", "lumen", m.date_of(2), 3)}
    assert set(rows) == {c.campaign_id for c in s.campaigns_for("lumen")}
    truth = [t for o in outs for t in o.truth if t.campaign_id == "lumen_meta_retargeting"]
    w = rows["lumen_meta_retargeting"]
    assert w.days_with_data == 3
    assert abs(w.spend - sum(t.spend for t in truth)) < 0.05
    assert w.conversions == sum(t.reported_conversions for t in truth)
    assert abs(w.revenue - sum(t.reported_revenue for t in truth)) < 0.05
    # a 1-day window only sees the last day; other experiments are invisible
    assert store.window_metrics("e", "lumen", m.date_of(2), 1)[0].days_with_data == 1
    assert store.window_metrics("other", "lumen", m.date_of(2), 3) == []
    series = store.daily_series("e", "lumen_meta_retargeting", m.date_of(2), 7)
    assert [p.day for p in series] == [m.date_of(d) for d in range(3)]
    store.reset("e")
    assert store.window_metrics("e", "lumen", m.date_of(2), 3) == []
