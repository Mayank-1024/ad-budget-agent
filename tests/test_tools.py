import json

from agent import tools


def test_tool_definitions_are_strict():
    for t in tools.TOOL_DEFINITIONS:
        assert t["strict"] is True
        assert t["input_schema"]["additionalProperties"] is False
        assert set(t["input_schema"]["required"]) == set(t["input_schema"]["properties"])
        assert "brand" not in json.dumps(t["input_schema"])  # brand comes from context only


def test_metrics_tool(lumen_ctx):
    content, err = tools.execute(lumen_ctx, "get_campaign_metrics", {"window_days": 7})
    assert not err
    data = json.loads(content)
    assert data["data_through"] == "2026-09-07"
    ids = {c["campaign_id"] for c in data["campaigns"]}
    assert ids == {c.campaign_id for c in lumen_ctx.campaigns}
    assert all(c["days_with_data"] == 7 and c["current_daily_budget"] for c in data["campaigns"])


def test_trend_tool(lumen_ctx):
    content, err = tools.execute(lumen_ctx, "get_daily_trend",
                                 {"campaign_id": "lumen_tiktok_ugc", "days": 7})
    assert not err and len(json.loads(content)["days"]) == 7


def test_tool_errors(lumen_ctx):
    for name, args, fragment in [
        ("get_campaign_metrics", {"window_days": 30}, "window_days"),
        ("get_daily_trend", {"campaign_id": "ridge_google_shopping", "days": 7}, "unknown"),
        ("get_daily_trend", {"campaign_id": "lumen_tiktok_ugc", "days": 5}, "days"),
        ("drop_table", {}, "unknown tool"),
    ]:
        content, err = tools.execute(lumen_ctx, name, args)
        assert err and fragment in content
