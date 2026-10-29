"""One brand, one day: propose -> guardrails -> store -> approve/execute.

    policy.propose (agent reads ClickHouse via tools; memory from Postgres)
        -> apply_guardrails (code)
        -> agent_runs, proposals, guardrail_events rows (Postgres)
        -> approval mode: auto-approve low risk / simulated reviewer / leave pending
        -> approved moves update campaigns.daily_budget in the same transaction

Decreases execute before increases so a reallocation never trips the brand cap halfway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from agent.guardrails import GuardrailConfig, apply_guardrails, tracking_suspects
from agent.tools import DayContext
from approvals.policy import MODES, classify_risk
from approvals.reviewer import SimulatedReviewer
from engine.policies import Policy
from storage.events import EventStore
from storage.models import ProposalRecord, RunRecord
from storage.state import CapExceededError, StaleProposalError, StateStore


@dataclass
class DayRecord:
    run: RunRecord
    proposals: list[ProposalRecord] = field(default_factory=list)
    interventions: int = 0


def run_brand_day(*, experiment_id: str, sim_day: date, brand_id: str, policy: Policy,
                  state: StateStore, events: EventStore, mode: str,
                  reviewer: SimulatedReviewer | None, use_memory: bool,
                  guard: GuardrailConfig | None = None) -> DayRecord:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    guard = guard or GuardrailConfig()
    brand = state.get_brand(experiment_id, brand_id)
    campaigns = state.list_campaigns(experiment_id, brand_id)
    ctx = DayContext(experiment_id, brand, campaigns, sim_day, events)
    memory = state.recall(experiment_id, brand_id, sim_day) if use_memory else None

    out = policy.propose(ctx, memory)
    window = events.window_metrics(experiment_id, brand_id, ctx.data_through,
                                   guard.tracking_lookback_days)
    result = apply_guardrails(brand, campaigns, out.requested,
                              tracking_suspects(window, guard), guard)

    ar = out.agent_run
    run = RunRecord(brand_id, sim_day, policy.name, policy.model, mode,
                    status="fallback" if ar and ar.fallback_reason else "ok",
                    fallback_reason=ar.fallback_reason if ar else None,
                    model_calls=ar.model_calls if ar else 0,
                    tool_calls=ar.tool_calls if ar else 0,
                    output_retries=ar.output_retries if ar else 0,
                    api_retries=ar.api_retries if ar else 0,
                    input_tokens=ar.input_tokens if ar else None,
                    output_tokens=ar.output_tokens if ar else None,
                    latency_ms=ar.latency_ms if ar else 0)
    state.record_run(experiment_id, run)
    record = DayRecord(run, interventions=len(result.interventions))

    for c in campaigns:
        cur, want, final = c.daily_budget, out.requested[c.campaign_id], result.final[
            c.campaign_id]
        if abs(want - cur) < 0.005:
            continue
        fired = result.rules_for(c.campaign_id)
        reason, effect = out.notes.get(c.campaign_id, ("", ""))
        p = ProposalRecord(
            run_id=run.run_id, brand_id=brand_id, campaign_id=c.campaign_id, sim_day=sim_day,
            direction="increase" if want > cur else "decrease", current_budget=cur,
            requested_budget=want, final_budget=final, reason=reason or "(none)",
            expected_effect=effect or "(none)",
            risk=classify_risk(cur, final, fired, c.campaign_id in out.flagged),
            status="blocked" if abs(final - cur) < 0.005 else "pending", guardrails=fired)
        state.add_proposal(experiment_id, p)
        for i in result.interventions:
            if i.campaign_id == c.campaign_id:
                state.add_guardrail_event(experiment_id, sim_day, i.rule, i.detail,
                                          run_id=run.run_id, proposal_id=p.proposal_id,
                                          campaign_id=c.campaign_id)
        record.proposals.append(p)

    pending = sorted((p for p in record.proposals if p.status == "pending"),
                     key=lambda p: p.final_budget - p.current_budget)  # decreases first
    for i, p in enumerate(pending):
        pending[i] = _approve_or_queue(experiment_id, p, policy, state, mode, reviewer)
    record.proposals = [next((q for q in pending if q.proposal_id == p.proposal_id), p)
                        for p in record.proposals]
    state.log(experiment_id, sim_day, "brand_day_done",
              {"brand_id": brand_id, "policy": policy.name, "status": run.status,
               "proposals": len(record.proposals), "interventions": record.interventions,
               "flags": sorted(out.flagged),
               "summary": ar.proposal.summary if ar and ar.proposal else None})
    return record


def _approve_or_queue(experiment_id: str, p: ProposalRecord, policy: Policy,
                      state: StateStore, mode: str,
                      reviewer: SimulatedReviewer | None) -> ProposalRecord:
    try:
        if not policy.needs_review or (mode == "automate" and p.risk == "low"):
            return state.auto_approve(experiment_id, p.proposal_id)
        if mode == "suggest" or reviewer is None:
            return p  # stays pending for a person (API / dashboard)
        review = reviewer.review(p)
        return state.decide(experiment_id, p.proposal_id, review.decision, reviewer.name,
                            review.reason, review.rule_id)
    except (CapExceededError, StaleProposalError) as exc:
        state.add_guardrail_event(experiment_id, p.sim_day, "execution_check", str(exc),
                                  run_id=p.run_id, proposal_id=p.proposal_id,
                                  campaign_id=p.campaign_id)
        return state.decide(experiment_id, p.proposal_id, "reject", "system", str(exc),
                            "execution_check")
