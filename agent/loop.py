"""The agent run for one brand on one day.

    day message (+ reviewer memory) -> model -> (tool calls -> ClickHouse -> model)* -> JSON
                                                                                    |
                                    validation: schema + semantics (one retry on failure)
                                                                                    |
                                        valid? requested budgets : fallback (hold all)

Tool budget: at most `max_tool_steps` tool calls. A batch that would go over is not run;
the model gets an is_error tool_result for each call saying the budget is used up and is
asked to answer with what it has. Asking for more tools after that ends the run.

The guardrails (agent/guardrails.py) run after this, on whatever budgets come out, in
engine/cycle.py. Every failure path (invalid output twice, step limit, model unavailable
after retries, non-retryable model error) ends in the same deterministic fallback: hold
every budget. Holding is the safe default for a budget agent: nothing changes until a
person or the next run decides otherwise.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agent import tools
from agent.model_client import ModelClient, ModelError, ModelTurn, TransientModelError
from agent.prompts import SYSTEM_PROMPT, day_message, validation_retry_message
from agent.proposal import (
    BudgetProposal,
    ProposalValidationError,
    proposal_json_schema,
    validate_proposal,
)
from agent.retry import call_with_retries
from agent.tools import DayContext
from storage.models import MemoryItem

BUDGET_EXHAUSTED = ("Error: today's tool-call budget is used up, so this call was not run. "
                    "Return your proposal now, using the data you already have.")


@dataclass
class LoopConfig:
    # Raised from 6 after the first real run (2026-10-29): Claude fetched daily trends for
    # several campaigns in one parallel batch and overshot 6 calls (see README, Evals).
    max_tool_steps: int = 10
    max_model_attempts: int = 3  # per model call, including the first


@dataclass
class AgentRun:
    proposal: BudgetProposal | None  # None when the run fell back
    requested: dict[str, float]  # campaign_id -> requested budget (current budget if held)
    fallback_reason: str | None = None
    model_calls: int = 0
    tool_calls: int = 0
    output_retries: int = 0
    api_retries: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0
    budget_exhausted: bool = False  # the model was told its tool budget is used up
    tools_called: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)

    def add_usage(self, turn: ModelTurn) -> None:
        if turn.input_tokens is not None:
            self.input_tokens = (self.input_tokens or 0) + turn.input_tokens
        if turn.output_tokens is not None:
            self.output_tokens = (self.output_tokens or 0) + turn.output_tokens


def run_agent_day(model: ModelClient, ctx: DayContext, memory: list[MemoryItem] | None,
                  config: LoopConfig | None = None,
                  sleep: Callable[[float], None] = time.sleep) -> AgentRun:
    config = config or LoopConfig()
    start = time.perf_counter()
    hold = {c.campaign_id: c.daily_budget for c in ctx.campaigns}
    run = AgentRun(proposal=None, requested=dict(hold))
    messages: list[dict[str, Any]] = [{"role": "user", "content": day_message(ctx, memory)}]
    schema = proposal_json_schema()

    def finish(proposal: BudgetProposal | None, reason: str | None) -> AgentRun:
        run.proposal, run.fallback_reason = proposal, reason
        run.requested = dict(hold)
        if proposal is not None:
            for m in proposal.moves:
                run.requested[m.campaign_id] = round(m.new_daily_budget, 2)
        run.latency_ms = round((time.perf_counter() - start) * 1000)
        return run

    while True:
        try:
            turn = _call_model(model, messages, schema, run, config, sleep)
        except TransientModelError:
            return finish(None, "model_unavailable")
        except ModelError:
            return finish(None, "model_error")

        messages.append({"role": "assistant", "content": turn.assistant_content})

        if turn.tool_calls:
            if run.tool_calls + len(turn.tool_calls) > config.max_tool_steps:
                # First time over budget: run none of these calls, tell the model, and let
                # it answer with the data it already has. Second time: fall back.
                if run.budget_exhausted:
                    return finish(None, "step_limit")
                run.budget_exhausted = True
                messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": call.id, "is_error": True,
                     "content": BUDGET_EXHAUSTED} for call in turn.tool_calls]})
                continue
            results = []
            for call in turn.tool_calls:
                run.tool_calls += 1
                run.tools_called.append(call.name)
                content, is_error = tools.execute(ctx, call.name, call.input)
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": content, "is_error": is_error})
            # all results for one assistant message go back in a single user message
            messages.append({"role": "user", "content": results})
            continue

        try:
            return finish(validate_proposal(turn.text, ctx.campaigns), None)
        except ProposalValidationError as err:
            run.validation_errors.append(str(err))
            if run.output_retries >= 1:
                return finish(None, "invalid_output")
            run.output_retries += 1
            messages.append({"role": "user", "content": validation_retry_message(str(err))})


def _call_model(model: ModelClient, messages: list[dict[str, Any]], schema: dict[str, Any],
                run: AgentRun, config: LoopConfig, sleep: Callable[[float], None]) -> ModelTurn:
    def attempt() -> ModelTurn:
        return model.complete(system=SYSTEM_PROMPT, messages=messages,
                              tools=tools.TOOL_DEFINITIONS, output_schema=schema)

    def on_retry(_attempt: int, _exc: Exception, _delay: float) -> None:
        run.api_retries += 1

    turn = call_with_retries(attempt, max_attempts=config.max_model_attempts, sleep=sleep,
                             on_retry=on_retry)
    run.model_calls += 1
    run.add_usage(turn)
    return turn
