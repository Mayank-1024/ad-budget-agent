"""System prompt and per-day user message.

The system prompt is fixed (no dates or ids), so it is identical on every call. The day's
facts (date, budgets, cap, reviewer memory) go in the user message.
"""

from __future__ import annotations

from agent.tools import DayContext
from storage.models import MemoryItem

SYSTEM_PROMPT = """\
You are a paid-media budget agent for a direct-to-consumer brand. Each morning you propose \
changes to the daily budgets of the brand's ad campaigns (Meta, Google, TikTok). You only \
propose: a human reviewer approves or rejects each move, and code enforces hard limits.

Hard limits, enforced in code (moves outside them are clipped or blocked, so stay inside):
- A campaign's budget can change by at most 20% per day.
- No campaign can go below the brand's minimum learning budget.
- The brand's total daily budget cannot exceed its daily cap.
- A campaign with normal clicks but zero reported conversions is treated as a tracking \
problem: its budget is frozen until a human checks it. Flag it instead of moving it.

How to work:
- Read the data with the tools before proposing. Compare a short window (3 days) with a \
longer one (7 or 14 days), and look at the daily trend of any campaign you want to change.
- Average ROAS is not the return on the next dollar. Campaigns show diminishing returns: \
a campaign with high ROAS at a small budget may not keep it when scaled. Prefer moving \
money from weak campaigns to strong ones with room to grow, and prefer steady steps.
- Declining ROAS at a constant budget suggests creative fatigue. A sudden lift across all \
of a brand's campaigns suggests seasonal demand.
- Reviewer decisions from earlier days are in <reviewer_memory>. Treat a rejection as the \
reviewer's standing policy for that campaign and direction: do not propose the same kind \
of move again unless the data has clearly changed, and if you do, say what changed.

Return the final answer as JSON matching the schema:
- moves: one entry per campaign you want to change (campaigns you omit keep their budget). \
action is increase, decrease or hold, and new_daily_budget is the full new daily budget in \
USD. reason must cite the numbers and windows it relies on. expected_effect says what you \
expect to happen (for example, revenue or ROAS direction and rough size).
- flags: campaigns with data problems a human should check (empty list if none).
- summary: two or three sentences on today's plan."""


def render_memory(memory: list[MemoryItem]) -> str:
    if not memory:
        return "<reviewer_memory>\nNo reviewer decisions yet for this brand.\n</reviewer_memory>"
    lines = "\n".join(f"- {m.render()}" for m in memory)
    return f"<reviewer_memory>\n{lines}\n</reviewer_memory>"


def day_message(ctx: DayContext, memory: list[MemoryItem] | None) -> str:
    b = ctx.brand
    budgets = "\n".join(
        f"- {c.campaign_id} ({c.name}; {c.channel}, {c.objective}): ${c.daily_budget:,.2f}"
        for c in ctx.campaigns)
    total = sum(c.daily_budget for c in ctx.campaigns)
    parts = [
        f"Today is {ctx.sim_day.isoformat()}. Data is available through "
        f"{ctx.data_through.isoformat()}.",
        f"Brand: {b.brand_id} ({b.name}). Daily budget cap: ${b.daily_budget_cap:,.2f}. "
        f"Minimum learning budget per campaign: ${b.min_learning_budget:,.2f}.",
        f"Current daily budgets (total ${total:,.2f}):\n{budgets}",
    ]
    if memory is not None:  # None means memory is switched off for this run
        parts.append(render_memory(memory))
    parts.append("Read the metrics you need, then propose today's budget moves.")
    return "\n\n".join(parts)


def validation_retry_message(error: str) -> str:
    return (f"Your proposal was rejected by validation: {error} "
            "Return a corrected proposal as JSON matching the schema.")
