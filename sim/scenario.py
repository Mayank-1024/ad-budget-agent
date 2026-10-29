"""The default synthetic scenario: three invented DTC brands, 11 campaigns.

Everything here is made up. The `hidden` fields (response curve, attribution
gap, fatigue, tracking break, seasonality, reviewer target ROAS) are ground
truth: the agent never sees them. It sees only what a real buyer would see,
namely the reported metrics in ClickHouse and the budgets in Postgres.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CampaignSpec:
    campaign_id: str
    brand_id: str
    name: str
    channel: str  # meta | google | tiktok
    objective: str  # prospecting | retargeting | search | shopping
    initial_budget: float
    # ---- hidden ground truth ----
    max_daily_conversions: float  # asymptote of the response curve
    saturation_spend: float  # spend where conversions reach ~63% of the asymptote
    aov: float  # average order value (USD)
    cpm: float  # cost per 1,000 impressions
    ctr: float  # click-through rate
    attribution_rate: float = 1.0  # share of true conversions the platform reports
    fatigue_per_day: float = 0.0  # creative fatigue: efficiency x (1 - f) per day
    fatigue_floor: float = 1.0
    tracking_breaks_on_day: int | None = None  # from this day on, 0 conversions are reported
    reviewer_tags: tuple[str, ...] = ()  # what the (simulated) human reviewer knows


@dataclass(frozen=True)
class BrandSpec:
    brand_id: str
    name: str
    daily_budget_cap: float
    min_learning_budget: float
    target_roas: float  # known to the reviewer, not given to the agent
    season: tuple[int, int, float] | None = None  # (first_day, last_day, demand multiplier)


@dataclass(frozen=True)
class Scenario:
    brands: tuple[BrandSpec, ...]
    campaigns: tuple[CampaignSpec, ...]
    warmup_days: int = 7  # days at initial budgets before any policy acts
    eval_days: int = 21
    start_date: str = "2026-09-01"
    notes: dict[str, str] = field(default_factory=dict)

    def brand(self, brand_id: str) -> BrandSpec:
        return next(b for b in self.brands if b.brand_id == brand_id)

    def campaign(self, campaign_id: str) -> CampaignSpec:
        return next(c for c in self.campaigns if c.campaign_id == campaign_id)

    def campaigns_for(self, brand_id: str) -> list[CampaignSpec]:
        return [c for c in self.campaigns if c.brand_id == brand_id]


def default_scenario(eval_days: int = 21, brand_ids: list[str] | None = None) -> Scenario:
    brands = (
        BrandSpec("lumen", "Lumen Skincare (synthetic)", daily_budget_cap=3400,
                  min_learning_budget=60, target_roas=2.0),
        BrandSpec("ridgeline", "Ridgeline Coffee (synthetic)", daily_budget_cap=2900,
                  min_learning_budget=60, target_roas=2.5),
        BrandSpec("kindred", "Kindred Pet Supply (synthetic)", daily_budget_cap=2300,
                  min_learning_budget=60, target_roas=2.2, season=(17, 21, 1.7)),
    )
    c = CampaignSpec
    campaigns = (
        # Lumen: prospecting looks bad on last-click but drives real sales; retargeting and
        # brand search have high average ROAS but are saturated; TikTok creative fatigues.
        c("lumen_meta_prospecting", "lumen", "Meta prospecting (broad)", "meta", "prospecting",
          1000, max_daily_conversions=95, saturation_spend=1800, aov=62, cpm=11, ctr=0.011,
          attribution_rate=0.45, reviewer_tags=("strategic_prospecting",)),
        c("lumen_meta_retargeting", "lumen", "Meta retargeting (site visitors)", "meta",
          "retargeting", 500, max_daily_conversions=48, saturation_spend=320, aov=58, cpm=19,
          ctr=0.018),
        c("lumen_google_brand", "lumen", "Google brand search", "google", "search", 400,
          max_daily_conversions=50, saturation_spend=110, aov=60, cpm=45, ctr=0.09,
          reviewer_tags=("demand_capped",)),
        c("lumen_tiktok_ugc", "lumen", "TikTok UGC creatives", "tiktok", "prospecting", 600,
          max_daily_conversions=70, saturation_spend=900, aov=48, cpm=7, ctr=0.009,
          fatigue_per_day=0.045, fatigue_floor=0.3),
        # Ridgeline: shopping has headroom; pmax is weak; TikTok tracking breaks on day 12.
        c("ridge_google_shopping", "ridgeline", "Google Shopping (all beans)", "google",
          "shopping", 800, max_daily_conversions=255, saturation_spend=2600, aov=36, cpm=14,
          ctr=0.014),
        c("ridge_meta_broad", "ridgeline", "Meta broad (subscriptions)", "meta", "prospecting",
          700, max_daily_conversions=98, saturation_spend=1300, aov=34, cpm=10, ctr=0.010),
        c("ridge_tiktok_spark", "ridgeline", "TikTok Spark ads", "tiktok", "prospecting", 500,
          max_daily_conversions=98, saturation_spend=1100, aov=33, cpm=6, ctr=0.010,
          tracking_breaks_on_day=12),
        c("ridge_google_pmax", "ridgeline", "Google Performance Max", "google", "prospecting",
          500, max_daily_conversions=39, saturation_spend=700, aov=35, cpm=9, ctr=0.008),
        # Kindred: a promo week lifts demand on days 17-21.
        c("kindred_meta_advantage", "kindred", "Meta Advantage+ shopping", "meta", "prospecting",
          900, max_daily_conversions=108, saturation_spend=1400, aov=44, cpm=12, ctr=0.012),
        c("kindred_google_search", "kindred", "Google non-brand search", "google", "search",
          700, max_daily_conversions=136, saturation_spend=1500, aov=42, cpm=30, ctr=0.05),
        c("kindred_tiktok_creators", "kindred", "TikTok creator whitelisting", "tiktok",
          "prospecting", 400, max_daily_conversions=36, saturation_spend=800, aov=40, cpm=6,
          ctr=0.009),
    )
    if brand_ids:
        brands = tuple(b for b in brands if b.brand_id in brand_ids)
        campaigns = tuple(x for x in campaigns if x.brand_id in brand_ids)
    return Scenario(brands=brands, campaigns=campaigns, eval_days=eval_days)
