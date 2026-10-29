from datetime import date

from agent.loop import LoopConfig, run_agent_day
from agent.prompts import SYSTEM_PROMPT
from agent.scripted_model import RulePlayingModel, ScriptedModel
from storage.models import MemoryItem

METRICS = {"tool_calls": [{"name": "get_campaign_metrics", "input": {"window_days": 7}}]}


def final(*moves):
    return {"final": {"moves": list(moves), "flags": [], "summary": "Today's plan."}}


def move(cid, budget, action="increase"):
    return {"campaign_id": cid, "action": action, "new_daily_budget": budget,
            "reason": "7-day ROAS 4.1, 3-day 4.0", "expected_effect": "about +5% revenue"}


def run(ctx, steps, memory=None):
    model = ScriptedModel(steps)
    return run_agent_day(model, ctx, memory, LoopConfig(), sleep=lambda s: None), model


def test_happy_path(lumen_ctx):
    r, model = run(lumen_ctx, [METRICS, final(move("lumen_meta_retargeting", 560))])
    assert r.fallback_reason is None and r.tool_calls == 1 and r.model_calls == 2
    assert r.requested["lumen_meta_retargeting"] == 560
    assert r.requested["lumen_google_brand"] == 400  # omitted campaigns are held
    # the tool result went back as one user message with a tool_result block
    blocks = model.seen_messages[1][-1]["content"]
    assert blocks[0]["type"] == "tool_result" and not blocks[0]["is_error"]


def test_one_retry_then_valid(lumen_ctx):
    bad = final(move("ridge_google_shopping", 900))  # another brand's campaign
    r, model = run(lumen_ctx, [METRICS, bad, final(move("lumen_meta_retargeting", 560))])
    assert r.fallback_reason is None and r.output_retries == 1
    assert "not a campaign of this brand" in model.seen_messages[2][-1]["content"]


def test_invalid_twice_falls_back_to_hold(lumen_ctx):
    r, _ = run(lumen_ctx, [METRICS, {"final_raw": "{oops"}, {"final_raw": "still bad"}])
    assert r.fallback_reason == "invalid_output" and r.proposal is None
    assert r.requested == {c.campaign_id: c.daily_budget for c in lumen_ctx.campaigns}
    assert len(r.validation_errors) == 2


def test_step_limit_asks_for_an_answer_first(lumen_ctx):
    """Over budget once: calls are not run, the model is told, and can still answer."""
    four = {"tool_calls": [{"name": "get_daily_trend",
                            "input": {"campaign_id": c.campaign_id, "days": 7}}
                           for c in lumen_ctx.campaigns]}
    model = ScriptedModel([METRICS, METRICS, METRICS, four,
                           final(move("lumen_meta_retargeting", 560))])
    r = run_agent_day(model, lumen_ctx, None, LoopConfig(max_tool_steps=6),
                      sleep=lambda s: None)
    assert r.fallback_reason is None and r.tool_calls == 3  # the batch of 4 was not run
    assert r.budget_exhausted
    told = model.seen_messages[4][-1]["content"]
    assert all(b["is_error"] and "budget is used up" in b["content"] for b in told)
    assert r.requested["lumen_meta_retargeting"] == 560


def test_step_limit_then_more_tools_falls_back(lumen_ctx):
    r, _ = run(lumen_ctx, [METRICS] * 12)
    assert r.fallback_reason == "step_limit" and r.tool_calls == 10


def test_transient_errors_are_retried(lumen_ctx):
    r, _ = run(lumen_ctx, [{"error": "transient"}, METRICS, final()])
    assert r.fallback_reason is None and r.api_retries == 1


def test_retries_exhausted(lumen_ctx):
    r, _ = run(lumen_ctx, [{"error": "transient"}] * 3)
    assert r.fallback_reason == "model_unavailable"


def test_fatal_error(lumen_ctx):
    r, _ = run(lumen_ctx, [{"error": "fatal"}])
    assert r.fallback_reason == "model_error" and r.proposal is None


def test_tool_error_goes_back_to_model(lumen_ctx):
    bad = {"tool_calls": [{"name": "get_daily_trend",
                           "input": {"campaign_id": "nope", "days": 7}}]}
    r, model = run(lumen_ctx, [bad, final()])
    block = model.seen_messages[1][-1]["content"][0]
    assert block["is_error"] and "unknown campaign_id" in block["content"]
    assert r.fallback_reason is None


def test_memory_block_in_prompt_only_when_enabled(lumen_ctx):
    mem = [MemoryItem("lumen", "lumen_google_brand", date(2026, 9, 7), "increase", 20.0,
                      "reject", "Brand search is capped.", "demand_capped")]
    _, with_mem = run(lumen_ctx, [final()], memory=mem)
    _, without = run(lumen_ctx, [final()], memory=None)
    first = with_mem.seen_messages[0][0]["content"]
    assert "<reviewer_memory>" in first and "REJECTED" in first and "capped" in first
    assert "<reviewer_memory>" not in without.seen_messages[0][0]["content"]


def test_system_prompt_is_static():
    assert "2026" not in SYSTEM_PROMPT


def test_rule_playing_model_respects_memory(lumen_ctx):
    mem = [MemoryItem("lumen", "lumen_google_brand", date(2026, 9, 7), "increase", 20.0,
                      "reject", "capped", "demand_capped")]
    r_mem = run_agent_day(RulePlayingModel(reads_memory=True), lumen_ctx, mem)
    r_no = run_agent_day(RulePlayingModel(reads_memory=False), lumen_ctx, mem)
    assert r_no.requested["lumen_google_brand"] > 400
    assert r_mem.requested["lumen_google_brand"] == 400
