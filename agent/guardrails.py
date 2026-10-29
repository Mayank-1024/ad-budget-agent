"""Budget guardrails, enforced in code after the proposal is validated.

The prompt tells the model these limits, but the prompt is not what enforces them: this
module is. Every policy (the Claude agent and both baselines) goes through the same
function, so a move outside the limits never reaches execution no matter who proposed it.

Order matters and is fixed:
1. tracking freeze: a campaign with normal clicks but zero reported conversions over the
   lookback window keeps its budget (no increase, no cut). The data cannot be trusted
   either way, so a human should look first. The ROAS of such a campaign reads as 0, which
   is exactly what would make a naive optimizer cut a campaign that may be working.
2. max daily change: clip to +/- max_change_pct of the current budget.
3. minimum learning budget: never below the brand's floor (pausing is a human action).
4. brand cap: if the total is above the daily cap, scale the increases down pro rata.

Each intervention is returned so it can be stored (guardrail_events) and counted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from storage.events import CampaignWindow
from storage.models import Brand, Campaign


@dataclass(frozen=True)
class GuardrailConfig:
    max_change_pct: float = 0.20
    tracking_lookback_days: int = 3
    tracking_min_clicks: int = 300


@dataclass(frozen=True)
class Intervention:
    rule: str  # tracking_freeze | max_change | min_learning | brand_cap
    campaign_id: str
    requested: float
    result: float
    detail: str


@dataclass
class GuardrailResult:
    final: dict[str, float]
    interventions: list[Intervention] = field(default_factory=list)

    def rules_for(self, campaign_id: str) -> list[str]:
        return [i.rule for i in self.interventions if i.campaign_id == campaign_id]


def tracking_suspects(window: list[CampaignWindow], cfg: GuardrailConfig) -> set[str]:
    """Campaigns whose tracking looks broken: real click volume, zero conversions."""
    return {w.campaign_id for w in window
            if w.clicks >= cfg.tracking_min_clicks and w.conversions == 0}


def apply_guardrails(brand: Brand, campaigns: list[Campaign], requested: dict[str, float],
                     suspects: set[str], cfg: GuardrailConfig | None = None) -> GuardrailResult:
    cfg = cfg or GuardrailConfig()
    current = {c.campaign_id: c.daily_budget for c in campaigns}
    result = GuardrailResult(final={})
    events = result.interventions

    for cid, cur in current.items():
        want = float(requested.get(cid, cur))
        new = want
        if cid in suspects and abs(new - cur) > 0.005:
            events.append(Intervention("tracking_freeze", cid, want, cur,
                                       f"clicks but 0 conversions in the last "
                                       f"{cfg.tracking_lookback_days} days; budget held"))
            new = cur
        lo, hi = cur * (1 - cfg.max_change_pct), cur * (1 + cfg.max_change_pct)
        if new > hi + 0.005 or new < lo - 0.005:
            clipped = min(max(new, lo), hi)
            events.append(Intervention("max_change", cid, want, round(clipped, 2),
                                       f"{(new - cur) / cur:+.0%} requested, limit is "
                                       f"+/-{cfg.max_change_pct:.0%} per day"))
            new = clipped
        if new < brand.min_learning_budget - 0.005:
            events.append(Intervention("min_learning", cid, want, brand.min_learning_budget,
                                       f"below the minimum learning budget "
                                       f"{brand.min_learning_budget:.2f}"))
            new = brand.min_learning_budget
        result.final[cid] = round(new, 2)

    total = sum(result.final.values())
    if total > brand.daily_budget_cap + 0.005:
        excess = total - brand.daily_budget_cap
        increases = {cid: result.final[cid] - current[cid] for cid in result.final
                     if result.final[cid] > current[cid]}
        pool = sum(increases.values())
        if pool > 0:
            share = min(1.0, excess / pool)
            for cid, inc in increases.items():
                scaled = round(current[cid] + inc * (1 - share), 2)
                events.append(Intervention("brand_cap", cid, result.final[cid], scaled,
                                           f"brand total {total:.2f} over cap "
                                           f"{brand.daily_budget_cap:.2f}; increase scaled by "
                                           f"{1 - share:.0%}"))
                result.final[cid] = scaled
            # rounding can leave a cent over the cap; take it from the largest increase
            over = round(sum(result.final.values()) - brand.daily_budget_cap, 2)
            if over > 0:
                top = max(increases, key=lambda c: result.final[c] - current[c])
                result.final[top] = round(result.final[top] - over, 2)
    return result
