import pytest

from agent.guardrails import GuardrailConfig, apply_guardrails, tracking_suspects
from storage.events import CampaignWindow


def rules(result):
    return sorted({i.rule for i in result.interventions})


def test_within_limits_untouched(brand, campaigns):
    r = apply_guardrails(brand, campaigns, {"c1": 440, "c2": 270}, set())
    assert r.final == {"c1": 440, "c2": 270, "c3": 200} and not r.interventions


@pytest.mark.parametrize("want, expected", [(800, 480), (100, 320)])
def test_max_daily_change_clipped(brand, campaigns, want, expected):
    r = apply_guardrails(brand, campaigns, {"c1": want}, set())
    assert r.final["c1"] == expected and rules(r) == ["max_change"]


def test_min_learning_floor(brand, campaigns):
    cfg = GuardrailConfig(max_change_pct=0.9)
    r = apply_guardrails(brand, campaigns, {"c3": 10}, set(), cfg)
    assert r.final["c3"] == 50 and "min_learning" in rules(r)


def test_brand_cap_scales_increases_pro_rata(brand, campaigns):
    # total 900 now; +80 +60 +40 would be 1080, cap 1000 -> keep 100/180 of each increase
    r = apply_guardrails(brand, campaigns, {"c1": 480, "c2": 360, "c3": 240}, set())
    assert sum(r.final.values()) == pytest.approx(1000, abs=0.01)
    assert r.final["c1"] == pytest.approx(400 + 80 * 100 / 180, abs=0.02)
    assert rules(r) == ["brand_cap"]


def test_reallocation_under_cap_is_fine(brand, campaigns):
    r = apply_guardrails(brand, campaigns, {"c1": 480, "c2": 240}, set())
    assert r.final["c1"] == 480 and not r.interventions


def test_tracking_suspect_is_frozen_both_ways(brand, campaigns):
    for want in (240, 160):
        r = apply_guardrails(brand, campaigns, {"c3": want}, {"c3"})
        assert r.final["c3"] == 200 and rules(r) == ["tracking_freeze"]


def test_holding_a_suspect_is_not_an_intervention(brand, campaigns):
    assert not apply_guardrails(brand, campaigns, {}, {"c3"}).interventions


def test_tracking_suspect_detection():
    cfg = GuardrailConfig()
    w = [CampaignWindow("broken", 3, 1500, 200000, 2500, 0, 0.0),
         CampaignWindow("tiny", 3, 30, 3000, 40, 0, 0.0),
         CampaignWindow("ok", 3, 1500, 200000, 2500, 40, 1600.0)]
    assert tracking_suspects(w, cfg) == {"broken"}


def test_requested_unknown_keys_are_ignored(brand, campaigns):
    r = apply_guardrails(brand, campaigns, {"other": 99999}, set())
    assert set(r.final) == {"c1", "c2", "c3"}
