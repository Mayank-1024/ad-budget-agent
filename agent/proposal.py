"""The strict JSON proposal the model must return, and its validation.

Two layers:
1. `parse_proposal`: JSON + Pydantic schema (extra keys forbidden, types, lengths).
2. `check_semantics`: rules a JSON schema cannot express: every campaign id belongs to
   this brand, no campaign appears twice, the action matches the budget it names.

Either failure raises ProposalValidationError, whose message goes back to the model for
one retry (agent/loop.py). Budget LIMITS (max change, cap, learning floor, tracking freeze)
are not validation errors: they are enforced afterwards by agent/guardrails.py, which clips
or blocks and records what it did.
"""

from __future__ import annotations

import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from storage.models import Campaign


class ProposalValidationError(Exception):
    pass


class Move(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    action: Literal["increase", "decrease", "hold"]
    new_daily_budget: float = Field(ge=0)
    reason: str = Field(min_length=10, max_length=600)
    expected_effect: str = Field(min_length=5, max_length=400)


class Flag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    issue: str = Field(min_length=5, max_length=400)


class BudgetProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moves: list[Move]
    flags: list[Flag]
    summary: str = Field(min_length=5, max_length=1200)


def proposal_json_schema() -> dict:
    """JSON Schema for structured outputs. Length limits are checked by Pydantic instead."""
    move = {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string"},
            "action": {"type": "string", "enum": ["increase", "decrease", "hold"]},
            "new_daily_budget": {"type": "number"},
            "reason": {"type": "string"},
            "expected_effect": {"type": "string"},
        },
        "required": ["campaign_id", "action", "new_daily_budget", "reason", "expected_effect"],
        "additionalProperties": False,
    }
    flag = {
        "type": "object",
        "properties": {"campaign_id": {"type": "string"}, "issue": {"type": "string"}},
        "required": ["campaign_id", "issue"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "moves": {"type": "array", "items": move},
            "flags": {"type": "array", "items": flag},
            "summary": {"type": "string"},
        },
        "required": ["moves", "flags", "summary"],
        "additionalProperties": False,
    }


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def parse_proposal(text: str) -> BudgetProposal:
    try:
        data = json.loads(_strip_code_fence(text))
    except json.JSONDecodeError as exc:
        raise ProposalValidationError(f"Final answer is not valid JSON ({exc.msg}).") from exc
    try:
        return BudgetProposal.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'root'}: {e['msg']}"
                             for e in exc.errors(include_url=False))
        raise ProposalValidationError(f"Final answer does not match the schema: {problems}"
                                      ) from exc


def check_semantics(p: BudgetProposal, campaigns: list[Campaign]) -> None:
    budgets = {c.campaign_id: c.daily_budget for c in campaigns}
    problems = []
    seen: set[str] = set()
    for m in p.moves:
        if m.campaign_id not in budgets:
            problems.append(f"{m.campaign_id!r} is not a campaign of this brand "
                            f"(valid: {sorted(budgets)})")
            continue
        if m.campaign_id in seen:
            problems.append(f"{m.campaign_id} appears more than once")
        seen.add(m.campaign_id)
        if not math.isfinite(m.new_daily_budget):
            problems.append(f"{m.campaign_id}: new_daily_budget must be a finite number")
            continue
        current, new = budgets[m.campaign_id], m.new_daily_budget
        if m.action == "hold" and abs(new - current) > 0.01:
            problems.append(f"{m.campaign_id}: action is hold but new_daily_budget {new:.2f} "
                            f"differs from the current {current:.2f}")
        if m.action == "increase" and new <= current:
            problems.append(f"{m.campaign_id}: action is increase but {new:.2f} <= current "
                            f"{current:.2f}")
        if m.action == "decrease" and new >= current:
            problems.append(f"{m.campaign_id}: action is decrease but {new:.2f} >= current "
                            f"{current:.2f}")
    for f in p.flags:
        if f.campaign_id not in budgets:
            problems.append(f"flag for unknown campaign {f.campaign_id!r}")
    if problems:
        raise ProposalValidationError("Proposal is inconsistent: " + "; ".join(problems))


def validate_proposal(text: str, campaigns: list[Campaign]) -> BudgetProposal:
    proposal = parse_proposal(text)
    check_semantics(proposal, campaigns)
    return proposal
