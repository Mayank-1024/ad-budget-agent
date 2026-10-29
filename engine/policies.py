"""Decision policies: the Claude agent and two baselines, behind one interface.

Every policy returns requested budgets. engine/cycle.py then applies the same guardrails
to all of them, so comparisons are about decisions, not about who obeyed the limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from agent.loop import AgentRun, LoopConfig, run_agent_day
from agent.model_client import ModelClient
from agent.tools import DayContext
from storage.models import MemoryItem


@dataclass
class PolicyOutput:
    requested: dict[str, float]
    notes: dict[str, tuple[str, str]] = field(default_factory=dict)  # cid -> (reason, effect)
    flagged: set[str] = field(default_factory=set)
    agent_run: AgentRun | None = None


class Policy(Protocol):
    name: str
    model: str
    needs_review: bool  # False: moves execute directly (baselines)

    def propose(self, ctx: DayContext, memory: list[MemoryItem] | None) -> PolicyOutput: ...


class HoldPolicy:
    name, model, needs_review = "hold", "none", False

    def propose(self, ctx, memory):
        return PolicyOutput({c.campaign_id: c.daily_budget for c in ctx.campaigns})


class RoasRulePolicy:
    """Scale campaigns with 7-day ROAS >= 2.5 by +20%, cut those under 1.5 by -20%."""

    name, model, needs_review = "roas_rule", "none", False

    def __init__(self, scale_above: float = 2.5, cut_below: float = 1.5, step: float = 0.20):
        self.scale_above, self.cut_below, self.step = scale_above, cut_below, step

    def propose(self, ctx, memory):
        window = {w.campaign_id: w for w in ctx.events.window_metrics(
            ctx.experiment_id, ctx.brand.brand_id, ctx.data_through, 7)}
        out = PolicyOutput({})
        for c in ctx.campaigns:
            w = window.get(c.campaign_id)
            roas = (w.roas or 0.0) if w else None
            new = c.daily_budget
            if roas is not None and roas >= self.scale_above:
                new = round(c.daily_budget * (1 + self.step), 2)
            elif roas is not None and roas < self.cut_below:
                new = round(c.daily_budget * (1 - self.step), 2)
            out.requested[c.campaign_id] = new
            if new != c.daily_budget:
                out.notes[c.campaign_id] = (f"7-day ROAS {roas:.2f}", "rule-based move")
        return out


class AgentPolicy:
    needs_review = True

    def __init__(self, model: ModelClient, config: LoopConfig | None = None,
                 name: str = "agent"):
        self.model_client, self.config, self.name = model, config or LoopConfig(), name
        self.model = model.name

    def propose(self, ctx, memory):
        run = run_agent_day(self.model_client, ctx, memory, self.config)
        out = PolicyOutput(dict(run.requested), agent_run=run)
        if run.proposal:
            for m in run.proposal.moves:
                out.notes[m.campaign_id] = (m.reason, m.expected_effect)
            out.flagged = {f.campaign_id for f in run.proposal.flags}
        return out
