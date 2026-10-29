from approvals.policy import classify_risk
from approvals.reviewer import SimulatedReviewer
from storage.models import ProposalRecord
from tests.conftest import EXP


def proposal(cid, brand, direction, cur=500.0, final=550.0, sim_day=None):
    return ProposalRecord(1, brand, cid, sim_day, direction, cur, final, final, "r", "e",
                          "high", "pending")


def test_reviewer_rules(seeded, scenario):
    _, events, market = seeded
    r = SimulatedReviewer(scenario, events, EXP)
    d = market.date_of(7)
    assert r.review(proposal("lumen_meta_prospecting", "lumen", "decrease", sim_day=d)
                    ).rule_id == "strategic_prospecting"
    assert r.review(proposal("lumen_meta_prospecting", "lumen", "increase", sim_day=d)
                    ).rule_id == "below_target"  # reported ROAS ~1.1 < 2.0
    assert r.review(proposal("lumen_google_brand", "lumen", "increase", sim_day=d)
                    ).rule_id == "demand_capped"
    assert r.review(proposal("lumen_google_brand", "lumen", "decrease", sim_day=d)
                    ).decision == "approve"
    ok = r.review(proposal("lumen_meta_retargeting", "lumen", "increase", sim_day=d))
    assert ok.decision == "approve" and ok.rule_id is None
    low = r.review(proposal("ridge_google_pmax", "ridgeline", "increase", sim_day=d))
    assert low.rule_id == "below_target" and "2.5" in low.reason


def test_risk_classification():
    assert classify_risk(100, 110, [], False) == "low"
    assert classify_risk(100, 90, [], False) == "low"
    assert classify_risk(100, 111, [], False) == "high"
    assert classify_risk(100, 105, ["brand_cap"], False) == "high"
    assert classify_risk(100, 105, [], True) == "high"
    assert classify_risk(100, 95, [], True) == "low"  # cutting a flagged campaign is low risk
