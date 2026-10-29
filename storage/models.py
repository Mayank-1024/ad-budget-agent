"""Plain records passed between the state store and the rest of the system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Brand:
    brand_id: str
    name: str
    daily_budget_cap: float
    min_learning_budget: float


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    brand_id: str
    name: str
    channel: str
    objective: str
    daily_budget: float


@dataclass
class RunRecord:
    brand_id: str
    sim_day: date
    policy: str
    model: str
    mode: str
    status: str = "ok"  # ok | fallback
    fallback_reason: str | None = None
    model_calls: int = 0
    tool_calls: int = 0
    output_retries: int = 0
    api_retries: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0
    run_id: int | None = None


@dataclass
class ProposalRecord:
    run_id: int
    brand_id: str
    campaign_id: str
    sim_day: date
    direction: str
    current_budget: float
    requested_budget: float
    final_budget: float
    reason: str
    expected_effect: str
    risk: str
    status: str
    guardrails: list[str] = field(default_factory=list)
    proposal_id: int | None = None
    decision: str | None = None
    decision_reason: str | None = None
    reviewer: str | None = None
    rule_id: str | None = None

    @property
    def change_pct(self) -> float:
        if not self.current_budget:
            return 0.0
        return round((self.final_budget - self.current_budget) / self.current_budget * 100, 2)

    def as_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d["sim_day"] = self.sim_day.isoformat()
        d["change_pct"] = self.change_pct
        return d


@dataclass(frozen=True)
class MemoryItem:
    brand_id: str
    campaign_id: str
    sim_day: date
    direction: str
    change_pct: float
    decision: str
    reason: str
    rule_id: str | None

    def render(self) -> str:
        verb = "approved" if self.decision == "approve" else "REJECTED"
        return (f"{self.sim_day.isoformat()}: {self.direction} {self.campaign_id} "
                f"({self.change_pct:+.1f}%) was {verb} by the reviewer: {self.reason}")
