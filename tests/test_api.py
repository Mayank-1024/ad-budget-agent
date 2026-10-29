import pytest
from fastapi.testclient import TestClient

from agent.scripted_model import RulePlayingModel
from api.main import app, get_events, get_state
from engine.cycle import run_brand_day
from engine.policies import AgentPolicy
from tests.conftest import EXP


@pytest.fixture
def client(seeded):
    state, events, market = seeded
    run_brand_day(experiment_id=EXP, sim_day=market.date_of(7), brand_id="lumen",
                  policy=AgentPolicy(RulePlayingModel()), state=state, events=events,
                  mode="approve", reviewer=None, use_memory=True)
    app.dependency_overrides[get_state] = lambda: state
    app.dependency_overrides[get_events] = lambda: events
    yield TestClient(app), state
    app.dependency_overrides.clear()


def test_lists(client):
    c, _ = client
    assert c.get("/healthz").json() == {"status": "ok"}
    assert c.get("/experiments").json() == [EXP]
    body = c.get(f"/experiments/{EXP}/campaigns").json()
    assert body["data_through"] == "2026-09-07" and len(body["campaigns"]) == 11
    assert body["campaigns"][0]["last_7_days"]["days_with_data"] == 7
    series = c.get(f"/experiments/{EXP}/campaigns/lumen_tiktok_ugc/daily?days=7").json()
    assert len(series) == 7 and series[-1]["day"] == "2026-09-07"
    assert c.get(f"/experiments/{EXP}/campaigns/nope/daily").status_code == 404
    assert c.get("/experiments/nope/proposals").status_code == 404


def test_approve_and_reject_from_queue(client):
    c, state = client
    pending = c.get(f"/experiments/{EXP}/proposals?status=pending").json()
    assert pending
    first, second = pending[0], pending[-1]
    r = c.post(f"/experiments/{EXP}/proposals/{first['proposal_id']}/decision",
               json={"decision": "approve", "reason": "looks right"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    budget = next(x.daily_budget for x in state.list_campaigns(EXP)
                  if x.campaign_id == first["campaign_id"])
    assert budget == first["final_budget"]
    again = c.post(f"/experiments/{EXP}/proposals/{first['proposal_id']}/decision",
                   json={"decision": "reject", "reason": "changed my mind"})
    assert again.status_code == 409
    if second["proposal_id"] != first["proposal_id"]:
        r = c.post(f"/experiments/{EXP}/proposals/{second['proposal_id']}/decision",
                   json={"decision": "reject", "reason": "not this week"})
        assert r.json()["decision_reason"] == "not this week"
        mem = state.recall(EXP, "lumen", state.list_proposals(EXP)[0].sim_day.replace(day=30))
        assert any(m.reason == "not this week" for m in mem)


def test_decision_validation(client):
    c, _ = client
    pid = c.get(f"/experiments/{EXP}/proposals").json()[0]["proposal_id"]
    url = f"/experiments/{EXP}/proposals/{pid}/decision"
    assert c.post(url, json={"decision": "maybe", "reason": "hmm"}).status_code == 422
    assert c.post(url, json={"decision": "approve", "reason": ""}).status_code == 422
    assert c.post(f"/experiments/{EXP}/proposals/99999/decision",
                  json={"decision": "approve", "reason": "ok ok"}).status_code == 404
