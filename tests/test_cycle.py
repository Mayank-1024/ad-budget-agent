import json

import pytest

from agent.scripted_model import ScriptedModel
from approvals.reviewer import SimulatedReviewer
from engine.cycle import run_brand_day
from engine.policies import AgentPolicy, HoldPolicy, RoasRulePolicy
from tests.conftest import EXP


def scripted(*moves, flags=()):
    return AgentPolicy(ScriptedModel([{"final": {"moves": list(moves), "flags": list(flags),
                                                 "summary": "today"}}]))


def mv(cid, budget):
    return {"campaign_id": cid, "action": "increase" if budget > 0 else "hold",
            "new_daily_budget": abs(budget), "reason": "7-day ROAS is strong",
            "expected_effect": "more revenue"}


def dec(cid, budget):
    return {**mv(cid, budget), "action": "decrease"}


def cycle(seeded, scenario, policy, mode, reviewer=True):
    state, events, market = seeded
    rev = SimulatedReviewer(scenario, events, EXP) if reviewer else None
    return run_brand_day(experiment_id=EXP, sim_day=market.date_of(7), brand_id="lumen",
                         policy=policy, state=state, events=events, mode=mode, reviewer=rev,
                         use_memory=True)


def budgets(state):
    return {c.campaign_id: c.daily_budget for c in state.list_campaigns(EXP, "lumen")}


def test_suggest_mode_never_executes(seeded, scenario):
    state = seeded[0]
    before = budgets(state)
    rec = cycle(seeded, scenario, scripted(mv("lumen_meta_retargeting", 550)), "suggest")
    assert [p.status for p in rec.proposals] == ["pending"]
    assert budgets(state) == before


def test_approve_mode_uses_reviewer(seeded, scenario):
    state = seeded[0]
    rec = cycle(seeded, scenario, scripted(mv("lumen_meta_retargeting", 550),
                                           mv("lumen_google_brand", 440)), "approve")
    status = {p.campaign_id: p.status for p in rec.proposals}
    assert status == {"lumen_meta_retargeting": "approved", "lumen_google_brand": "rejected"}
    assert budgets(state)["lumen_meta_retargeting"] == 550
    assert budgets(state)["lumen_google_brand"] == 400


def test_approve_mode_without_reviewer_queues(seeded, scenario):
    rec = cycle(seeded, scenario, scripted(mv("lumen_meta_retargeting", 550)), "approve",
                reviewer=False)
    assert rec.proposals[0].status == "pending"


def test_automate_mode_auto_approves_low_risk_only(seeded, scenario):
    state = seeded[0]
    rec = cycle(seeded, scenario, scripted(mv("lumen_meta_retargeting", 540),  # +8%
                                           mv("lumen_tiktok_ugc", 720)), "automate")  # +20%
    status = {p.campaign_id: (p.risk, p.status) for p in rec.proposals}
    assert status["lumen_meta_retargeting"] == ("low", "auto_approved")
    assert status["lumen_tiktok_ugc"] == ("high", "approved")  # went to the reviewer
    assert budgets(state)["lumen_meta_retargeting"] == 540


def test_guardrail_clip_is_recorded(seeded, scenario):
    state = seeded[0]
    rec = cycle(seeded, scenario, scripted(mv("lumen_tiktok_ugc", 1200)), "approve")
    p = rec.proposals[0]
    assert (p.requested_budget, p.final_budget, p.guardrails) == (1200, 720, ["max_change"])
    assert [g["rule"] for g in state.list_guardrail_events(EXP)] == ["max_change"]


def test_reallocation_executes_decreases_first(seeded, scenario):
    state = seeded[0]
    # total 2500, cap 3400: push to the cap with a reallocation
    policy = scripted(dec("lumen_google_brand", 320), mv("lumen_meta_retargeting", 600),
                      mv("lumen_tiktok_ugc", 720))
    cycle(seeded, scenario, policy, "automate")
    assert sum(budgets(state).values()) <= 3400


def test_fallback_run_is_recorded_and_holds(seeded, scenario):
    state = seeded[0]
    before = budgets(state)
    rec = cycle(seeded, scenario, AgentPolicy(ScriptedModel([{"final_raw": "x"},
                                                             {"final_raw": "y"}])), "approve")
    assert rec.run.status == "fallback" and rec.run.fallback_reason == "invalid_output"
    assert rec.proposals == [] and budgets(state) == before


def test_baselines_execute_directly(seeded, scenario):
    state = seeded[0]
    rec = cycle(seeded, scenario, RoasRulePolicy(), "approve")
    assert rec.proposals and all(p.status in ("auto_approved", "blocked")
                                 for p in rec.proposals)
    assert cycle(seeded, scenario, HoldPolicy(), "approve").proposals == []
    assert state.recall(EXP, "lumen", seeded[2].date_of(9)) == []


def test_bad_mode(seeded, scenario):
    with pytest.raises(ValueError):
        cycle(seeded, scenario, HoldPolicy(), "yolo")


def test_audit_log_written(seeded, scenario):
    state = seeded[0]
    cycle(seeded, scenario, scripted(mv("lumen_meta_retargeting", 550)), "approve")
    events = [a["event"] for a in state.audit]
    assert "proposal_approved" in events and events[-1] == "brand_day_done"
    json.dumps(state.audit, default=str)
