"""HTTP API for the approval queue and campaign metrics (used by the React dashboard).

The API never calls the model. It reads proposals and budgets from Postgres, metrics from
ClickHouse, and records human approve/reject decisions through the same
StateStore.decide used by the simulated reviewer, so a human decision also lands in
decision memory and executes the budget change in the same transaction.

    uv run uvicorn api.main:app --port 8000
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from settings import get_settings
from storage.state import CapExceededError, StaleProposalError, StateError

app = FastAPI(title="Ad Budget Agent", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@lru_cache(maxsize=1)
def _stores() -> tuple[Any, Any]:
    from storage.events import ClickHouseEventStore
    from storage.state import PostgresStateStore

    s = get_settings()
    return PostgresStateStore.connect(s.database_url), ClickHouseEventStore.connect(s)


def get_state() -> Any:
    return _stores()[0]


def get_events() -> Any:
    return _stores()[1]


State = Annotated[Any, Depends(get_state)]
Events = Annotated[Any, Depends(get_events)]


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=500)
    reviewer: str = Field(default="human", min_length=1, max_length=80)


def _brand_ids(state: Any, experiment_id: str) -> list[str]:
    brands = state.list_brands(experiment_id)
    if not brands:
        raise HTTPException(404, f"unknown experiment {experiment_id}")
    return [b.brand_id for b in brands]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/experiments")
def experiments(state: State) -> list[str]:
    return state.list_experiments()


@app.get("/experiments/{experiment_id}/campaigns")
def campaigns(experiment_id: str, state: State, events: Events) -> dict[str, Any]:
    _brand_ids(state, experiment_id)
    latest = events.latest_day(experiment_id)
    window = {}
    if latest:
        for b in state.list_brands(experiment_id):
            for w in events.window_metrics(experiment_id, b.brand_id, latest, 7):
                window[w.campaign_id] = w.as_dict()
    return {
        "data_through": latest.isoformat() if latest else None,
        "brands": [{"brand_id": b.brand_id, "name": b.name, "daily_budget_cap":
                    b.daily_budget_cap, "min_learning_budget": b.min_learning_budget}
                   for b in state.list_brands(experiment_id)],
        "campaigns": [{"campaign_id": c.campaign_id, "brand_id": c.brand_id, "name": c.name,
                       "channel": c.channel, "objective": c.objective,
                       "daily_budget": c.daily_budget, "last_7_days": window.get(c.campaign_id)}
                      for c in state.list_campaigns(experiment_id)],
    }


@app.get("/experiments/{experiment_id}/campaigns/{campaign_id}/daily")
def daily(experiment_id: str, campaign_id: str, state: State, events: Events,
          days: Annotated[int, Query(ge=1, le=60)] = 28,
          end: date | None = None) -> list[dict[str, Any]]:
    _brand_ids(state, experiment_id)
    if campaign_id not in {c.campaign_id for c in state.list_campaigns(experiment_id)}:
        raise HTTPException(404, f"unknown campaign {campaign_id}")
    end = end or events.latest_day(experiment_id)
    if end is None:
        return []
    return [p.as_dict() for p in events.daily_series(experiment_id, campaign_id, end, days)]


@app.get("/experiments/{experiment_id}/proposals")
def proposals(experiment_id: str, state: State, status: str | None = None,
              brand_id: str | None = None) -> list[dict[str, Any]]:
    _brand_ids(state, experiment_id)
    rows = state.list_proposals(experiment_id, status=status, brand_id=brand_id)
    return [p.as_dict() for p in sorted(rows, key=lambda p: p.proposal_id or 0, reverse=True)]


@app.post("/experiments/{experiment_id}/proposals/{proposal_id}/decision")
def decide(experiment_id: str, proposal_id: int, body: Decision,
           state: State) -> dict[str, Any]:
    try:
        p = state.decide(experiment_id, proposal_id, body.decision, body.reviewer,
                         body.reason, rule_id=None)
    except (StaleProposalError, CapExceededError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except StateError as exc:
        code = 404 if "unknown" in str(exc) else 409
        raise HTTPException(code, str(exc)) from exc
    return p.as_dict()


@app.get("/experiments/{experiment_id}/guardrails")
def guardrails(experiment_id: str, state: State) -> list[dict[str, Any]]:
    _brand_ids(state, experiment_id)
    return [{**g, "sim_day": str(g["sim_day"])} for g in state.list_guardrail_events(
        experiment_id)]
