import json

import pytest

from agent.proposal import ProposalValidationError, proposal_json_schema, validate_proposal


def move(cid="c1", action="increase", budget=440.0, **kw):
    return {"campaign_id": cid, "action": action, "new_daily_budget": budget,
            "reason": "7-day ROAS 3.1 vs 3-day 3.0", "expected_effect": "more revenue", **kw}


def doc(*moves, flags=()):
    return json.dumps({"moves": list(moves), "flags": list(flags), "summary": "Plan for today."})


def test_valid_proposal(campaigns):
    p = validate_proposal(doc(move(), move("c2", "decrease", 250.0)), campaigns)
    assert [m.campaign_id for m in p.moves] == ["c1", "c2"]


def test_code_fence_is_tolerated(campaigns):
    assert validate_proposal("```json\n" + doc(move()) + "\n```", campaigns).moves


@pytest.mark.parametrize("text, fragment", [
    ("not json", "not valid JSON"),
    (json.dumps({"moves": [], "flags": []}), "summary"),
    (json.dumps({"moves": [], "flags": [], "summary": "ok plan", "extra": 1}), "extra"),
    (doc(move(reason="short")), "reason"),
    (doc(move(budget=-5)), "new_daily_budget"),
    (doc(move(action="pause")), "action"),
])
def test_schema_errors(campaigns, text, fragment):
    with pytest.raises(ProposalValidationError, match=fragment):
        validate_proposal(text, campaigns)


@pytest.mark.parametrize("moves, fragment", [
    ([move("zz")], "not a campaign of this brand"),
    ([move(), move()], "more than once"),
    ([move(action="hold", budget=410)], "action is hold"),
    ([move(action="increase", budget=390)], "action is increase"),
    ([move(action="decrease", budget=420)], "action is decrease"),
])
def test_semantic_errors(campaigns, moves, fragment):
    with pytest.raises(ProposalValidationError, match=fragment):
        validate_proposal(doc(*moves), campaigns)


def test_flag_for_unknown_campaign(campaigns):
    with pytest.raises(ProposalValidationError, match="unknown campaign"):
        validate_proposal(doc(flags=[{"campaign_id": "zz", "issue": "broken pixel"}]), campaigns)


def test_json_schema_is_closed():
    s = proposal_json_schema()
    assert s["additionalProperties"] is False
    item = s["properties"]["moves"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
