"""A simulated human reviewer for evals.

It knows things the agent is never told (the rules below and each brand's target ROAS),
the way a real media buyer knows the brand's strategy. When it rejects a move it says
why, and that reason is what lands in decision memory. The memory eval measures whether
the agent stops re-proposing moves after being told no.

Rules, checked in order (first match rejects):
- strategic_prospecting: never cut a campaign tagged strategic prospecting. In the
  simulator this campaign reports only part of its true sales (an attribution gap), so
  the rule is right on ground truth: cutting it loses real revenue.
- demand_capped: never scale a campaign tagged demand capped (brand search). In the
  simulator it is saturated, so extra budget buys almost nothing.
- below_target: never scale a campaign whose 7-day reported ROAS is under the brand's
  target ROAS.
Everything else is approved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sim.scenario import Scenario
from storage.events import EventStore
from storage.models import ProposalRecord


@dataclass(frozen=True)
class Review:
    decision: str  # approve | reject
    reason: str
    rule_id: str | None


class SimulatedReviewer:
    name = "simulated-reviewer"

    def __init__(self, scenario: Scenario, events: EventStore, experiment_id: str):
        self.scenario, self.events, self.experiment_id = scenario, events, experiment_id

    def review(self, p: ProposalRecord) -> Review:
        spec = self.scenario.campaign(p.campaign_id)
        brand = self.scenario.brand(p.brand_id)
        if p.direction == "decrease" and "strategic_prospecting" in spec.reviewer_tags:
            return Review("reject", "This is our top-of-funnel prospecting campaign. "
                          "Last-click ROAS undercounts it because it feeds retargeting and "
                          "search, so we do not cut it on reported ROAS.",
                          "strategic_prospecting")
        if p.direction == "increase" and "demand_capped" in spec.reviewer_tags:
            return Review("reject", "Brand search is capped by branded query volume. More "
                          "budget will not buy more conversions, so we do not scale it.",
                          "demand_capped")
        if p.direction == "increase":
            window = self.events.window_metrics(self.experiment_id, p.brand_id,
                                                p.sim_day - timedelta(days=1), 7)
            row = next((w for w in window if w.campaign_id == p.campaign_id), None)
            roas = (row.roas or 0.0) if row else 0.0
            if roas < brand.target_roas:
                return Review("reject", f"We do not scale campaigns below the brand's target "
                              f"ROAS of {brand.target_roas:.1f}; 7-day ROAS is {roas:.2f}.",
                              "below_target")
        return Review("approve", "Within policy.", None)
