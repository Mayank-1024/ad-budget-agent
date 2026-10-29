"""The tools the model can call. Each one runs a fixed, parameterized ClickHouse query.

The model chooses a window length from a fixed set and a campaign id; code checks the id
belongs to the brand in context (the brand itself is never a model argument), so a run
can only ever read its own brand's data. Results are compact JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from storage.events import EventStore
from storage.models import Brand, Campaign

WINDOWS = [1, 3, 7, 14]
TREND_DAYS = [7, 14]


@dataclass
class DayContext:
    experiment_id: str
    brand: Brand
    campaigns: list[Campaign]  # with today's budgets
    sim_day: date  # the day being planned; data is available through sim_day - 1
    events: EventStore

    @property
    def data_through(self) -> date:
        return self.sim_day - timedelta(days=1)


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_campaign_metrics",
        "description": (
            "Reported performance of every campaign of this brand over the last N days "
            "(ending yesterday): spend, impressions, clicks, conversions, revenue, ROAS "
            "(revenue/spend), CPA (spend/conversion), CTR, CVR, plus today's daily budget. "
            "Compare a short and a long window to see trends."),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"window_days": {"type": "integer", "enum": WINDOWS}},
            "required": ["window_days"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_daily_trend",
        "description": (
            "Day-by-day reported spend, clicks, conversions, revenue and ROAS for one "
            "campaign of this brand, for the last 7 or 14 days ending yesterday. Use it to "
            "spot fatigue, spikes, or tracking problems before changing a budget."),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "string"},
                "days": {"type": "integer", "enum": TREND_DAYS},
            },
            "required": ["campaign_id", "days"],
            "additionalProperties": False,
        },
    },
]


class ToolError(Exception):
    pass


def _metrics(ctx: DayContext, args: dict[str, Any]) -> dict[str, Any]:
    window = args.get("window_days")
    if window not in WINDOWS:
        raise ToolError(f"window_days must be one of {WINDOWS}")
    budgets = {c.campaign_id: c.daily_budget for c in ctx.campaigns}
    rows = ctx.events.window_metrics(ctx.experiment_id, ctx.brand.brand_id, ctx.data_through,
                                     window)
    return {"window_days": window, "data_through": ctx.data_through.isoformat(),
            "campaigns": [{**r.as_dict(), "current_daily_budget": budgets.get(r.campaign_id)}
                          for r in rows]}


def _trend(ctx: DayContext, args: dict[str, Any]) -> dict[str, Any]:
    cid, days = args.get("campaign_id"), args.get("days")
    if cid not in {c.campaign_id for c in ctx.campaigns}:
        raise ToolError(f"unknown campaign_id {cid!r} for this brand")
    if days not in TREND_DAYS:
        raise ToolError(f"days must be one of {TREND_DAYS}")
    rows = ctx.events.daily_series(ctx.experiment_id, cid, ctx.data_through, days)
    return {"campaign_id": cid, "days": [r.as_dict() for r in rows]}


HANDLERS = {"get_campaign_metrics": _metrics, "get_daily_trend": _trend}


def execute(ctx: DayContext, name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """Returns (content, is_error). Errors go back to the model as tool_result errors."""
    handler = HANDLERS.get(name)
    if handler is None:
        return f"Error: unknown tool {name!r}", True
    try:
        return json.dumps(handler(ctx, args)), False
    except ToolError as exc:
        return f"Error: {exc}", True
