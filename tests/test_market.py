from sim.market import Market, poisson
from sim.scenario import default_scenario


def budgets(s, scale=1.0, **override):
    b = {c.campaign_id: c.initial_budget * scale for c in s.campaigns}
    b.update(override)
    return b


def test_same_seed_same_outcome():
    s = default_scenario()
    a = Market(s, seed=3).simulate_day(4, budgets(s))
    b = Market(s, seed=3).simulate_day(4, budgets(s))
    assert a.truth == b.truth and a.conversions == b.conversions and a.hourly == b.hourly


def test_common_random_numbers_per_campaign():
    """Changing one campaign's budget must not change another campaign's outcome."""
    s = default_scenario()
    m = Market(s, seed=3)
    a = m.simulate_day(4, budgets(s))
    b = m.simulate_day(4, budgets(s, lumen_tiktok_ugc=900))
    other = [t for t in a.truth if t.campaign_id != "lumen_tiktok_ugc"]
    assert other == [t for t in b.truth if t.campaign_id != "lumen_tiktok_ugc"]


def test_diminishing_returns():
    s = default_scenario()
    m = Market(s)
    for c in s.campaigns:
        lo = m.marginal_roas(c.campaign_id, c.initial_budget * 0.5, 0)
        hi = m.marginal_roas(c.campaign_id, c.initial_budget * 1.5, 0)
        assert hi < lo


def test_tracking_break_reports_zero_but_truth_is_positive():
    s = default_scenario()
    m = Market(s)
    before = {t.campaign_id: t for t in m.simulate_day(11, budgets(s)).truth}
    after = {t.campaign_id: t for t in m.simulate_day(12, budgets(s)).truth}
    assert before["ridge_tiktok_spark"].reported_conversions > 0
    assert after["ridge_tiktok_spark"].reported_conversions == 0
    assert after["ridge_tiktok_spark"].true_conversions > 0
    out = m.simulate_day(12, budgets(s))
    assert not [c for c in out.conversions if c.campaign_id == "ridge_tiktok_spark"]
    clicks = sum(h.clicks for h in out.hourly if h.campaign_id == "ridge_tiktok_spark")
    assert clicks > 300  # clicks keep flowing, which is what makes it look broken


def test_attribution_gap_on_prospecting():
    s = default_scenario()
    t = {r.campaign_id: r for r in Market(s).simulate_day(0, budgets(s)).truth}
    p = t["lumen_meta_prospecting"]
    assert p.reported_revenue < 0.7 * p.true_revenue
    r = t["lumen_meta_retargeting"]
    assert r.reported_revenue == r.true_revenue


def test_fatigue_and_season():
    s = default_scenario()
    m = Market(s)
    ugc = s.campaign("lumen_tiktok_ugc")
    assert m.efficiency(ugc, 20) < 0.5 * m.efficiency(ugc, 0)
    kin = s.campaign("kindred_google_search")
    assert m.efficiency(kin, 18) == 1.7 and m.efficiency(kin, 10) == 1.0


def test_event_rows_are_consistent():
    s = default_scenario()
    out = Market(s).simulate_day(0, budgets(s))
    assert len(out.hourly) == 24 * len(s.campaigns)
    for t in out.truth:
        hours = [h for h in out.hourly if h.campaign_id == t.campaign_id]
        assert abs(sum(h.spend for h in hours) - t.spend) < 0.05
        events = [c for c in out.conversions if c.campaign_id == t.campaign_id]
        assert len(events) == t.reported_conversions
        assert all(h.clicks <= h.impressions for h in hours)


def test_poisson_mean():
    import random

    rng = random.Random(1)
    for lam in (3.0, 80.0):
        xs = [poisson(rng, lam) for _ in range(4000)]
        assert abs(sum(xs) / len(xs) - lam) < 0.05 * lam
    assert poisson(rng, 0) == 0
