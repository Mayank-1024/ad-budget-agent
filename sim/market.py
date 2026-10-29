"""Synthetic ad market: turns daily budgets into event-level data plus hidden ground truth.

For campaign c on day d with spend s, expected TRUE conversions are

    max_conv * (1 - exp(-s / saturation)) * fatigue(d) * season(d)

which is concave in spend (diminishing returns). Realized conversions are Poisson around
that, each with a lognormal order value. The platform then REPORTS only part of them:
`attribution_rate` of them (an attribution gap) and none at all once tracking breaks.

Outputs per simulated day:
- hourly ad stats rows (impressions, clicks, spend) and one row per reported conversion,
  which is what lands in ClickHouse and what the agent can query;
- ground-truth rows (true conversions, true revenue, expected revenue) that only the
  eval scorer reads.

Randomness uses one RNG per (seed, campaign, day), so two policies that set the same
budget for a campaign on a day get exactly the same outcome (common random numbers),
which makes policy comparisons much less noisy.
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sim.scenario import CampaignSpec, Scenario

# share of a day's delivery in each UTC hour (evening-heavy), sums to 1
_DIURNAL_RAW = [0.6 + 0.4 * math.sin((h - 9) / 24 * 2 * math.pi) for h in range(24)]
DIURNAL = [w / sum(_DIURNAL_RAW) for w in _DIURNAL_RAW]
_LOGNORM_SIGMA = 0.35
_LOGNORM_MEAN = math.exp(_LOGNORM_SIGMA**2 / 2)


@dataclass(frozen=True)
class HourlyStat:
    brand_id: str
    campaign_id: str
    channel: str
    ts: datetime
    impressions: int
    clicks: int
    spend: float


@dataclass(frozen=True)
class ConversionEvent:
    brand_id: str
    campaign_id: str
    channel: str
    ts: datetime
    event_id: str
    order_value: float


@dataclass(frozen=True)
class TruthRow:
    day: int
    brand_id: str
    campaign_id: str
    spend: float
    true_conversions: int
    true_revenue: float
    expected_revenue: float  # noise-free, the main eval metric
    reported_conversions: int
    reported_revenue: float


@dataclass
class DayOutcome:
    hourly: list[HourlyStat]
    conversions: list[ConversionEvent]
    truth: list[TruthRow]


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 40:  # normal approximation is accurate here and avoids a long loop
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


class Market:
    def __init__(self, scenario: Scenario, seed: int = 7):
        self.scenario = scenario
        self.seed = seed
        self.start = date.fromisoformat(scenario.start_date)

    def date_of(self, day: int) -> date:
        return self.start + timedelta(days=day)

    # ---- hidden ground truth ----
    def efficiency(self, c: CampaignSpec, day: int) -> float:
        mult = max(c.fatigue_floor, (1 - c.fatigue_per_day) ** day) if c.fatigue_per_day else 1.0
        season = self.scenario.brand(c.brand_id).season
        if season and season[0] <= day <= season[1]:
            mult *= season[2]
        return mult

    def expected_conversions(self, c: CampaignSpec, spend: float, day: int) -> float:
        curve = c.max_daily_conversions * (1 - math.exp(-spend / c.saturation_spend))
        return curve * self.efficiency(c, day)

    def expected_revenue(self, campaign_id: str, spend: float, day: int) -> float:
        c = self.scenario.campaign(campaign_id)
        return self.expected_conversions(c, spend, day) * c.aov

    def marginal_roas(self, campaign_id: str, spend: float, day: int, step: float = 1.0) -> float:
        """True revenue from the next dollar (finite difference)."""
        return (self.expected_revenue(campaign_id, spend + step, day)
                - self.expected_revenue(campaign_id, spend, day)) / step

    # ---- one simulated day ----
    def simulate_day(self, day: int, budgets: dict[str, float]) -> DayOutcome:
        out = DayOutcome([], [], [])
        midnight = datetime.combine(self.date_of(day), datetime.min.time(), tzinfo=UTC)
        for c in self.scenario.campaigns:
            budget = float(budgets.get(c.campaign_id, 0.0))
            rng = random.Random(f"{self.seed}:{c.campaign_id}:{day}")
            spend = round(budget * rng.uniform(0.96, 1.0), 2)  # platforms rarely spend 100%
            cpm = c.cpm * rng.uniform(0.9, 1.1)
            ctr = c.ctr * rng.uniform(0.9, 1.1)
            hourly_spend = [spend * w for w in DIURNAL]
            for h, s in enumerate(hourly_spend):
                impressions = poisson(rng, s / cpm * 1000)
                clicks = min(impressions, poisson(rng, impressions * ctr))
                out.hourly.append(HourlyStat(c.brand_id, c.campaign_id, c.channel,
                                             midnight + timedelta(hours=h), impressions, clicks,
                                             round(s, 4)))
            expected = self.expected_conversions(c, spend, day)
            n_true = poisson(rng, expected)
            broken = c.tracking_breaks_on_day is not None and day >= c.tracking_breaks_on_day
            true_rev = rep_rev = 0.0
            n_rep = 0
            for _ in range(n_true):
                value = round(c.aov * rng.lognormvariate(0, _LOGNORM_SIGMA) / _LOGNORM_MEAN, 2)
                hour = rng.choices(range(24), weights=DIURNAL)[0]
                reported = rng.random() < c.attribution_rate
                true_rev += value
                if reported and not broken:
                    n_rep += 1
                    rep_rev += value
                    ts = midnight + timedelta(hours=hour, seconds=rng.randrange(3600))
                    event_id = str(uuid.UUID(int=rng.getrandbits(128), version=4))
                    out.conversions.append(ConversionEvent(c.brand_id, c.campaign_id, c.channel,
                                                           ts, event_id, value))
            out.truth.append(TruthRow(day, c.brand_id, c.campaign_id, spend, n_true,
                                      round(true_rev, 2), round(expected * c.aov, 2), n_rep,
                                      round(rep_rev, 2)))
        return out
