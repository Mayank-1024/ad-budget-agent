"""Event store: where performance data lives and how the agent reads it.

Two implementations with the same interface:
- ClickHouseEventStore: the real one (MergeTree tables + materialized-view rollup).
- MemoryEventStore: plain Python, so unit tests and the offline eval need no Docker.
  tests/test_db_integration.py checks both return the same numbers for the same data.

Derived ratios (ROAS, CPA, CTR, CVR) are computed in one place (`CampaignWindow`) from
summed totals, never by averaging daily ratios.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from sim.market import DayOutcome
from storage import queries

SCHEMA_PATH = Path(__file__).parent / "clickhouse" / "schema.sql"


def _ratio(num: float, den: float) -> float | None:
    return round(num / den, 4) if den else None


@dataclass(frozen=True)
class CampaignWindow:
    campaign_id: str
    days_with_data: int
    spend: float
    impressions: int
    clicks: int
    conversions: int
    revenue: float

    @property
    def roas(self) -> float | None:
        return _ratio(self.revenue, self.spend)

    @property
    def cpa(self) -> float | None:
        return _ratio(self.spend, self.conversions)

    @property
    def ctr(self) -> float | None:
        return _ratio(self.clicks, self.impressions)

    @property
    def cvr(self) -> float | None:
        return _ratio(self.conversions, self.clicks)

    def as_dict(self) -> dict[str, Any]:
        return {"campaign_id": self.campaign_id, "days_with_data": self.days_with_data,
                "spend": round(self.spend, 2), "impressions": self.impressions,
                "clicks": self.clicks, "conversions": self.conversions,
                "revenue": round(self.revenue, 2), "roas": self.roas, "cpa": self.cpa,
                "ctr": self.ctr, "cvr": self.cvr}


@dataclass(frozen=True)
class DailyPoint:
    day: date
    spend: float
    impressions: int
    clicks: int
    conversions: int
    revenue: float

    @property
    def roas(self) -> float | None:
        return _ratio(self.revenue, self.spend)

    def as_dict(self) -> dict[str, Any]:
        return {"day": self.day.isoformat(), "spend": round(self.spend, 2),
                "impressions": self.impressions, "clicks": self.clicks,
                "conversions": self.conversions, "revenue": round(self.revenue, 2),
                "roas": self.roas}


def window_bounds(end_day: date, days: int) -> tuple[date, date]:
    return end_day - timedelta(days=days - 1), end_day


class EventStore(Protocol):
    def reset(self, experiment_id: str) -> None: ...
    def insert_day(self, experiment_id: str, outcome: DayOutcome) -> None: ...
    def window_metrics(self, experiment_id: str, brand_id: str, end_day: date,
                       days: int) -> list[CampaignWindow]: ...
    def daily_series(self, experiment_id: str, campaign_id: str, end_day: date,
                     days: int) -> list[DailyPoint]: ...
    def latest_day(self, experiment_id: str) -> date | None: ...


class MemoryEventStore:
    """Keeps the same rows ClickHouse would, aggregated per (experiment, campaign, day)."""

    def __init__(self) -> None:
        # (experiment, campaign) -> day -> [spend, impressions, clicks, conversions, revenue]
        self._daily: dict[tuple[str, str], dict[date, list[float]]] = defaultdict(dict)
        self._brand_of: dict[str, str] = {}
        self.raw_rows = 0

    def reset(self, experiment_id: str) -> None:
        for key in [k for k in self._daily if k[0] == experiment_id]:
            del self._daily[key]

    def _bucket(self, experiment_id: str, brand_id: str, campaign_id: str, day: date) -> list:
        self._brand_of[campaign_id] = brand_id
        return self._daily[(experiment_id, campaign_id)].setdefault(day, [0.0, 0, 0, 0, 0.0])

    def insert_day(self, experiment_id: str, outcome: DayOutcome) -> None:
        for h in outcome.hourly:
            b = self._bucket(experiment_id, h.brand_id, h.campaign_id, h.ts.date())
            b[0] += h.spend
            b[1] += h.impressions
            b[2] += h.clicks
        for c in outcome.conversions:
            b = self._bucket(experiment_id, c.brand_id, c.campaign_id, c.ts.date())
            b[3] += 1
            b[4] += c.order_value
        self.raw_rows += len(outcome.hourly) + len(outcome.conversions)

    def window_metrics(self, experiment_id: str, brand_id: str, end_day: date,
                       days: int) -> list[CampaignWindow]:
        start, end = window_bounds(end_day, days)
        out = []
        for (exp, cid), by_day in sorted(self._daily.items()):
            if exp != experiment_id or self._brand_of.get(cid) != brand_id:
                continue
            rows = [v for d, v in by_day.items() if start <= d <= end]
            if not rows:
                continue
            out.append(CampaignWindow(cid, len(rows), sum(r[0] for r in rows),
                                      int(sum(r[1] for r in rows)), int(sum(r[2] for r in rows)),
                                      int(sum(r[3] for r in rows)), sum(r[4] for r in rows)))
        return out

    def daily_series(self, experiment_id: str, campaign_id: str, end_day: date,
                     days: int) -> list[DailyPoint]:
        start, end = window_bounds(end_day, days)
        by_day = self._daily.get((experiment_id, campaign_id), {})
        return [DailyPoint(d, v[0], int(v[1]), int(v[2]), int(v[3]), v[4])
                for d, v in sorted(by_day.items()) if start <= d <= end]

    def latest_day(self, experiment_id: str) -> date | None:
        days = [d for (e, _), by_day in self._daily.items() if e == experiment_id
                for d in by_day]
        return max(days) if days else None


class ClickHouseEventStore:
    def __init__(self, client: Any):
        self.client = client

    @classmethod
    def connect(cls, settings: Any) -> ClickHouseEventStore:
        import clickhouse_connect

        client = clickhouse_connect.get_client(
            host=settings.clickhouse_host, port=settings.clickhouse_port,
            username=settings.clickhouse_user, password=settings.clickhouse_password,
            database=settings.clickhouse_db)
        store = cls(client)
        store.apply_schema()
        return store

    def apply_schema(self) -> None:
        for statement in SCHEMA_PATH.read_text().split("\n;\n"):
            sql = "\n".join(line for line in statement.splitlines()
                            if not line.strip().startswith("--")).strip().rstrip(";")
            if sql:
                self.client.command(sql)

    def reset(self, experiment_id: str) -> None:
        for table in ("ad_stats_hourly", "conversion_events", "campaign_daily"):
            self.client.command(
                f"ALTER TABLE {table} DELETE WHERE experiment_id = {{e:String}} "
                "SETTINGS mutations_sync = 2", parameters={"e": experiment_id})

    def insert_day(self, experiment_id: str, outcome: DayOutcome) -> None:
        if outcome.hourly:
            self.client.insert(
                "ad_stats_hourly",
                [[experiment_id, h.brand_id, h.campaign_id, h.channel, h.ts, h.impressions,
                  h.clicks, Decimal(str(h.spend))] for h in outcome.hourly],
                column_names=["experiment_id", "brand_id", "campaign_id", "channel", "ts",
                              "impressions", "clicks", "spend"])
        if outcome.conversions:
            self.client.insert(
                "conversion_events",
                [[experiment_id, c.brand_id, c.campaign_id, c.channel, c.ts,
                  uuid.UUID(c.event_id), Decimal(str(c.order_value))]
                 for c in outcome.conversions],
                column_names=["experiment_id", "brand_id", "campaign_id", "channel", "ts",
                              "event_id", "order_value"])

    def window_metrics(self, experiment_id: str, brand_id: str, end_day: date,
                       days: int) -> list[CampaignWindow]:
        start, end = window_bounds(end_day, days)
        result = self.client.query(queries.WINDOW_METRICS, parameters={
            "experiment_id": experiment_id, "brand_id": brand_id,
            "start_day": start, "end_day": end})
        return [CampaignWindow(r[0], int(r[1]), float(r[2]), int(r[3]), int(r[4]), int(r[5]),
                               float(r[6])) for r in result.result_rows]

    def daily_series(self, experiment_id: str, campaign_id: str, end_day: date,
                     days: int) -> list[DailyPoint]:
        start, end = window_bounds(end_day, days)
        result = self.client.query(queries.DAILY_SERIES, parameters={
            "experiment_id": experiment_id, "campaign_id": campaign_id,
            "start_day": start, "end_day": end})
        return [DailyPoint(r[0], float(r[1]), int(r[2]), int(r[3]), int(r[4]), float(r[5]))
                for r in result.result_rows]

    def latest_day(self, experiment_id: str) -> date | None:
        result = self.client.query(
            "SELECT max(day), count() FROM campaign_daily WHERE experiment_id = {e:String}",
            parameters={"e": experiment_id})
        day, n = result.result_rows[0]
        return day if n else None

    def raw_daily_check(self, experiment_id: str, campaign_id: str) -> list[tuple]:
        result = self.client.query(queries.RAW_DAILY_CHECK, parameters={
            "experiment_id": experiment_id, "campaign_id": campaign_id})
        return [tuple(r) for r in result.result_rows]
