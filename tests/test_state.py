"""MemoryStateStore behavior. tests/test_db_integration.py runs the same checks on Postgres."""

import pytest

from storage.models import ProposalRecord, RunRecord
from storage.state import CapExceededError, MemoryStateStore, StaleProposalError, StateError
from tests.conftest import day

EXP = "s"


@pytest.fixture
def store(brand, campaigns):
    s = MemoryStateStore()
    s.setup_experiment(EXP, [brand], campaigns)
    return s


def propose(store, cid, cur, final, d=7, direction=None):
    rid = store.record_run(EXP, RunRecord("b1", day(d), "agent", "m", "approve"))
    p = ProposalRecord(rid, "b1", cid, day(d), direction or ("increase" if final > cur
                       else "decrease"), cur, final, final, "reason here", "effect", "high",
                       "pending")
    store.add_proposal(EXP, p)
    return p


def budget(store, cid):
    return next(c.daily_budget for c in store.list_campaigns(EXP) if c.campaign_id == cid)


def test_approve_executes_and_remembers(store):
    p = propose(store, "c1", 400, 480)
    out = store.decide(EXP, p.proposal_id, "approve", "rev", "fine")
    assert out.status == "approved" and budget(store, "c1") == 480
    assert store.recall(EXP, "b1", day(8))[0].decision == "approve"


def test_reject_does_not_execute(store):
    p = propose(store, "c2", 300, 240)
    store.decide(EXP, p.proposal_id, "reject", "rev", "keep it", "strategic_prospecting")
    assert budget(store, "c2") == 300
    m = store.recall(EXP, "b1", day(8))[0]
    assert (m.decision, m.rule_id, m.change_pct) == ("reject", "strategic_prospecting", -20.0)


def test_cannot_decide_twice(store):
    p = propose(store, "c1", 400, 480)
    store.decide(EXP, p.proposal_id, "reject", "rev", "no")
    with pytest.raises(StateError, match="not pending"):
        store.decide(EXP, p.proposal_id, "approve", "rev", "yes")


def test_stale_proposal_refused(store):
    p = propose(store, "c1", 400, 480)
    store.set_budget(EXP, "c1", day(7), 420, "human")
    with pytest.raises(StaleProposalError):
        store.decide(EXP, p.proposal_id, "approve", "rev", "ok")
    assert store.get_proposal(EXP, p.proposal_id).status == "pending"


def test_cap_checked_at_execution(store):
    a, b = propose(store, "c1", 400, 480), propose(store, "c2", 300, 360)
    store.decide(EXP, a.proposal_id, "approve", "rev", "ok")
    store.set_budget(EXP, "c3", day(7), 200, "human")  # total now 980
    with pytest.raises(CapExceededError):
        store.decide(EXP, b.proposal_id, "approve", "rev", "ok")


def test_recall_latest_per_key_rejections_first(store):
    for d, decision in [(7, "reject"), (8, "reject"), (9, "approve")]:
        p = propose(store, "c1", budget(store, "c1"), budget(store, "c1") * 1.1, d=d)
        store.decide(EXP, p.proposal_id, decision, "rev", f"day {d}")
    p = propose(store, "c2", 300, 270, d=9)
    store.decide(EXP, p.proposal_id, "reject", "rev", "c2 no")
    got = store.recall(EXP, "b1", day(10))
    assert [(m.campaign_id, m.decision, m.reason) for m in got] == [
        ("c2", "reject", "c2 no"), ("c1", "reject", "day 8"), ("c1", "approve", "day 9")]
    assert store.recall(EXP, "b1", day(8))[0].reason == "day 7"  # no peeking at the future
    assert store.recall("other", "b1", day(10)) == []


def test_auto_approve(store):
    p = propose(store, "c3", 200, 210)
    assert store.auto_approve(EXP, p.proposal_id).status == "auto_approved"
    assert budget(store, "c3") == 210
    assert store.recall(EXP, "b1", day(8)) == []  # memory holds reviewer decisions only
