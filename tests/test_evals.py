import json

from agent.scripted_model import RulePlayingModel
from engine.policies import AgentPolicy, HoldPolicy, RoasRulePolicy
from engine.simulation import run_experiment
from evals import run as cli
from evals.metrics import score
from sim.scenario import default_scenario
from storage.events import MemoryEventStore
from storage.state import MemoryStateStore


def experiment(policy, use_memory=True, days=6, mode="approve"):
    return run_experiment(experiment_id=f"t-{policy.name}-{use_memory}",
                          scenario=default_scenario(eval_days=days), policy=policy,
                          state=MemoryStateStore(), events=MemoryEventStore(), mode=mode,
                          use_memory=use_memory)


def test_hold_baseline_never_proposes():
    s = score(experiment(HoldPolicy(), use_memory=False), 0.1, 0.5)
    assert s["proposals"] == 0 and s["spend"] > 0 and s["true_roas"] > 0
    assert s["eval_days"] == 6 and s["runs"] == 18


def test_truth_counts_unreported_revenue():
    s = score(experiment(HoldPolicy(), use_memory=False), 0.1, 0.5)
    assert s["realized_true_revenue"] > s["reported_revenue"]  # attribution gap + broken pixel


def test_roas_rule_trips_tracking_freeze():
    s = score(experiment(RoasRulePolicy(), use_memory=False, days=10), 0.1, 0.5)
    assert s["guardrail_interventions"].get("tracking_freeze", 0) >= 1


def test_memory_reduces_repeated_rejections():
    with_mem = score(experiment(AgentPolicy(RulePlayingModel(True), name="agent")), 0.1, 0.5)
    no_mem = score(experiment(AgentPolicy(RulePlayingModel(False), name="agent_no_memory"),
                              use_memory=False), 0.1, 0.5)
    assert no_mem["repeated_rejections"] > 0
    assert with_mem["repeated_rejections"] < no_mem["repeated_rejections"]


def test_repeat_counting():
    s = score(experiment(AgentPolicy(RulePlayingModel(False), name="x"), use_memory=False,
                         days=3), 0.1, 0.5)
    # each rule that fires on day 1 repeats on days 2 and 3
    assert s["repeated_rejections"] == 2 * len(s["rejections_by_rule"])


def test_cli_offline_writes_reports(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPORTS", tmp_path)
    assert cli.main(["--days", "2", "--brands", "lumen", "--tag", "t"]) == 0
    data = json.loads((tmp_path / "t.json").read_text())
    assert [s["policy"] for s in data["scores"]] == ["hold", "roas_rule", "agent",
                                                    "agent_no_memory"]
    assert "not an LLM" in data["meta"]["model"]
    assert "| agent |" in (tmp_path / "t.md").read_text()


def test_budget_guard_stops_calls():
    import pytest

    from agent.model_client import ModelTurn

    class Fake:
        name = "fake"

        def complete(self, **kw):
            return ModelTurn([], [], "", "end_turn", input_tokens=1_000_000, output_tokens=0)

    guard = cli.BudgetGuard(Fake(), budget_usd=0.15, price_in=0.10, price_out=0.50)
    guard.complete()
    guard.complete()
    with pytest.raises(cli.BudgetExceeded):
        guard.complete()
