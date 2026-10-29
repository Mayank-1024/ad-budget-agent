"""State store: budgets, proposals, approvals, guardrail events, memory, audit log.

Two implementations with the same interface:
- PostgresStateStore: the real one (storage/postgres/migrations/*.sql).
- MemoryStateStore: plain Python for unit tests and the offline eval.

The interesting invariants live in `decide` / `auto_approve`: recording a decision,
writing it to memory, and executing the budget change happen together (one Postgres
transaction), and execution refuses a stale proposal (the budget changed since it was
proposed) or one that would push the brand over its daily cap.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from storage.models import Brand, Campaign, MemoryItem, ProposalRecord, RunRecord

MIGRATIONS_DIR = Path(__file__).parent / "postgres" / "migrations"


class StateError(Exception):
    pass


class StaleProposalError(StateError):
    """The campaign's budget changed after the proposal was made."""


class CapExceededError(StateError):
    """Executing the proposal would put the brand over its daily budget cap."""


class StateStore(Protocol):
    def setup_experiment(self, experiment_id: str, brands: list[Brand],
                         campaigns: list[Campaign]) -> None: ...
    def list_experiments(self) -> list[str]: ...
    def list_brands(self, experiment_id: str) -> list[Brand]: ...
    def get_brand(self, experiment_id: str, brand_id: str) -> Brand: ...
    def list_campaigns(self, experiment_id: str, brand_id: str | None = None
                       ) -> list[Campaign]: ...
    def set_budget(self, experiment_id: str, campaign_id: str, sim_day: date,
                   new_budget: float, source: str, proposal_id: int | None = None) -> None: ...
    def record_run(self, experiment_id: str, run: RunRecord) -> int: ...
    def list_runs(self, experiment_id: str) -> list[RunRecord]: ...
    def add_proposal(self, experiment_id: str, p: ProposalRecord) -> int: ...
    def get_proposal(self, experiment_id: str, proposal_id: int) -> ProposalRecord: ...
    def list_proposals(self, experiment_id: str, status: str | None = None,
                       brand_id: str | None = None) -> list[ProposalRecord]: ...
    def add_guardrail_event(self, experiment_id: str, sim_day: date, rule: str, detail: str,
                            run_id: int | None = None, proposal_id: int | None = None,
                            campaign_id: str | None = None) -> None: ...
    def list_guardrail_events(self, experiment_id: str) -> list[dict[str, Any]]: ...
    def decide(self, experiment_id: str, proposal_id: int, decision: str, reviewer: str,
               reason: str, rule_id: str | None = None) -> ProposalRecord: ...
    def auto_approve(self, experiment_id: str, proposal_id: int) -> ProposalRecord: ...
    def recall(self, experiment_id: str, brand_id: str, before_day: date,
               limit: int = 8) -> list[MemoryItem]: ...
    def log(self, experiment_id: str, sim_day: date, event: str,
            payload: dict[str, Any]) -> None: ...


def _check_executable(p: ProposalRecord, campaigns: list[Campaign], cap: float) -> None:
    current = next(c for c in campaigns if c.campaign_id == p.campaign_id).daily_budget
    if abs(current - p.current_budget) > 0.005:
        raise StaleProposalError(
            f"proposal {p.proposal_id}: budget is now {current:.2f}, "
            f"proposal was made against {p.current_budget:.2f}")
    total = sum(c.daily_budget for c in campaigns if c.campaign_id != p.campaign_id)
    if total + p.final_budget > cap + 0.005:
        raise CapExceededError(
            f"proposal {p.proposal_id}: brand total would be {total + p.final_budget:.2f} "
            f"over cap {cap:.2f}")


def _select_memory(rows: list[tuple[int, MemoryItem]], limit: int) -> list[MemoryItem]:
    """Latest decision per (campaign, direction, decision); rejections first, newest first."""
    latest: dict[tuple[str, str, str], tuple[int, MemoryItem]] = {}
    for mid, m in rows:
        key = (m.campaign_id, m.direction, m.decision)
        if key not in latest or (m.sim_day, mid) > (latest[key][1].sim_day, latest[key][0]):
            latest[key] = (mid, m)
    ordered = sorted(latest.values(),
                     key=lambda r: (r[1].decision == "reject", r[1].sim_day, r[0]), reverse=True)
    return [m for _, m in ordered[:limit]]


class MemoryStateStore:
    def __init__(self) -> None:
        self.brands: dict[tuple[str, str], Brand] = {}
        self.campaigns: dict[tuple[str, str], Campaign] = {}
        self.runs: dict[int, tuple[str, RunRecord]] = {}
        self.proposals: dict[int, tuple[str, ProposalRecord]] = {}
        self.guardrail_events: list[dict[str, Any]] = []
        self.memory: list[tuple[str, int, MemoryItem]] = []
        self.budget_changes: list[dict[str, Any]] = []
        self.audit: list[dict[str, Any]] = []
        self._ids = itertools.count(1)

    def setup_experiment(self, experiment_id, brands, campaigns):
        for store in (self.brands, self.campaigns):
            for k in [k for k in store if k[0] == experiment_id]:
                del store[k]
        for b in brands:
            self.brands[(experiment_id, b.brand_id)] = b
        for c in campaigns:
            self.campaigns[(experiment_id, c.campaign_id)] = c

    def list_experiments(self):
        return sorted({k[0] for k in self.brands})

    def list_brands(self, experiment_id):
        return [b for (e, _), b in sorted(self.brands.items()) if e == experiment_id]

    def get_brand(self, experiment_id, brand_id):
        try:
            return self.brands[(experiment_id, brand_id)]
        except KeyError:
            raise StateError(f"unknown brand {brand_id}") from None

    def list_campaigns(self, experiment_id, brand_id=None):
        return [c for (e, _), c in sorted(self.campaigns.items())
                if e == experiment_id and (brand_id is None or c.brand_id == brand_id)]

    def set_budget(self, experiment_id, campaign_id, sim_day, new_budget, source,
                   proposal_id=None):
        c = self.campaigns[(experiment_id, campaign_id)]
        self.budget_changes.append({"experiment_id": experiment_id, "campaign_id": campaign_id,
                                    "sim_day": sim_day, "old": c.daily_budget,
                                    "new": round(new_budget, 2), "source": source,
                                    "proposal_id": proposal_id})
        self.campaigns[(experiment_id, campaign_id)] = replace(c, daily_budget=round(new_budget, 2))

    def record_run(self, experiment_id, run):
        run.run_id = next(self._ids)
        self.runs[run.run_id] = (experiment_id, run)
        return run.run_id

    def list_runs(self, experiment_id):
        return [r for e, r in self.runs.values() if e == experiment_id]

    def add_proposal(self, experiment_id, p):
        p.proposal_id = next(self._ids)
        self.proposals[p.proposal_id] = (experiment_id, p)
        return p.proposal_id

    def get_proposal(self, experiment_id, proposal_id):
        e, p = self.proposals.get(proposal_id, (None, None))
        if e != experiment_id:
            raise StateError(f"unknown proposal {proposal_id}")
        return p

    def list_proposals(self, experiment_id, status=None, brand_id=None):
        return [p for e, p in self.proposals.values() if e == experiment_id
                and (status is None or p.status == status)
                and (brand_id is None or p.brand_id == brand_id)]

    def add_guardrail_event(self, experiment_id, sim_day, rule, detail, run_id=None,
                            proposal_id=None, campaign_id=None):
        self.guardrail_events.append({"experiment_id": experiment_id, "sim_day": sim_day,
                                      "rule": rule, "detail": detail, "run_id": run_id,
                                      "proposal_id": proposal_id, "campaign_id": campaign_id})

    def list_guardrail_events(self, experiment_id):
        return [g for g in self.guardrail_events if g["experiment_id"] == experiment_id]

    def _execute(self, experiment_id, p):
        cap = self.get_brand(experiment_id, p.brand_id).daily_budget_cap
        _check_executable(p, self.list_campaigns(experiment_id, p.brand_id), cap)
        self.set_budget(experiment_id, p.campaign_id, p.sim_day, p.final_budget, "agent",
                        p.proposal_id)

    def decide(self, experiment_id, proposal_id, decision, reviewer, reason, rule_id=None):
        p = self.get_proposal(experiment_id, proposal_id)
        if p.status != "pending":
            raise StateError(f"proposal {proposal_id} is {p.status}, not pending")
        if decision not in ("approve", "reject"):
            raise StateError(f"bad decision {decision!r}")
        if decision == "approve":
            self._execute(experiment_id, p)  # raises before anything is recorded
        p.status = "approved" if decision == "approve" else "rejected"
        p.decision, p.decision_reason, p.reviewer, p.rule_id = decision, reason, reviewer, rule_id
        self.memory.append((experiment_id, next(self._ids), MemoryItem(
            p.brand_id, p.campaign_id, p.sim_day, p.direction, p.change_pct, decision, reason,
            rule_id)))
        self.log(experiment_id, p.sim_day, f"proposal_{p.status}",
                 {"proposal_id": proposal_id, "reviewer": reviewer, "reason": reason})
        return p

    def auto_approve(self, experiment_id, proposal_id):
        p = self.get_proposal(experiment_id, proposal_id)
        if p.status != "pending":
            raise StateError(f"proposal {proposal_id} is {p.status}, not pending")
        self._execute(experiment_id, p)
        p.status = "auto_approved"
        self.log(experiment_id, p.sim_day, "proposal_auto_approved", {"proposal_id": proposal_id})
        return p

    def recall(self, experiment_id, brand_id, before_day, limit=8):
        rows = [(mid, m) for e, mid, m in self.memory
                if e == experiment_id and m.brand_id == brand_id and m.sim_day < before_day]
        return _select_memory(rows, limit)

    def log(self, experiment_id, sim_day, event, payload):
        self.audit.append({"experiment_id": experiment_id, "sim_day": sim_day, "event": event,
                           "payload": payload})


class PostgresStateStore:
    def __init__(self, conn: Any):
        self.conn = conn

    @classmethod
    def connect(cls, database_url: str) -> PostgresStateStore:
        import psycopg

        store = cls(psycopg.connect(database_url, autocommit=True))
        store.migrate()
        return store

    def migrate(self) -> list[str]:
        applied = []
        with self.conn.transaction():
            self.conn.execute("SELECT pg_advisory_xact_lock(4242)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                              "(version text PRIMARY KEY, applied_at timestamptz DEFAULT now())")
            done = {r[0] for r in self.conn.execute("SELECT version FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.stem not in done:
                    self.conn.execute(path.read_text())
                    self.conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)",
                                      (path.stem,))
                    applied.append(path.stem)
        return applied

    def _rows(self, sql: str, params: tuple = ()) -> list[tuple]:
        return self.conn.execute(sql, params).fetchall()

    # ---- setup and reads ----
    def setup_experiment(self, experiment_id, brands, campaigns):
        with self.conn.transaction():
            for table in ("decision_log", "decision_memory", "guardrail_events", "agent_runs",
                          "brands"):  # brands cascades to campaigns, proposals, budget_changes
                self.conn.execute(f"DELETE FROM {table} WHERE experiment_id = %s",
                                  (experiment_id,))
            for b in brands:
                self.conn.execute("INSERT INTO brands VALUES (%s, %s, %s, %s, %s)",
                                  (experiment_id, b.brand_id, b.name, b.daily_budget_cap,
                                   b.min_learning_budget))
            for c in campaigns:
                self.conn.execute("INSERT INTO campaigns VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                  (experiment_id, c.campaign_id, c.brand_id, c.name, c.channel,
                                   c.objective, c.daily_budget))

    def list_experiments(self):
        return [r[0] for r in self._rows("SELECT DISTINCT experiment_id FROM brands ORDER BY 1")]

    def list_brands(self, experiment_id):
        return [Brand(r[0], r[1], float(r[2]), float(r[3])) for r in self._rows(
            "SELECT brand_id, name, daily_budget_cap, min_learning_budget FROM brands "
            "WHERE experiment_id = %s ORDER BY brand_id", (experiment_id,))]

    def get_brand(self, experiment_id, brand_id):
        for b in self.list_brands(experiment_id):
            if b.brand_id == brand_id:
                return b
        raise StateError(f"unknown brand {brand_id}")

    def list_campaigns(self, experiment_id, brand_id=None, *, for_update=False):
        sql = ("SELECT campaign_id, brand_id, name, channel, objective, daily_budget "
               "FROM campaigns WHERE experiment_id = %s AND (%s::text IS NULL OR brand_id = %s) "
               "ORDER BY campaign_id")
        if for_update:
            sql += " FOR UPDATE"
        return [Campaign(r[0], r[1], r[2], r[3], r[4], float(r[5]))
                for r in self._rows(sql, (experiment_id, brand_id, brand_id))]

    def set_budget(self, experiment_id, campaign_id, sim_day, new_budget, source,
                   proposal_id=None):
        with self.conn.transaction():
            self.conn.execute(
                "INSERT INTO budget_changes (experiment_id, campaign_id, sim_day, old_budget, "
                "new_budget, source, proposal_id) SELECT experiment_id, campaign_id, %s, "
                "daily_budget, %s, %s, %s FROM campaigns WHERE experiment_id = %s "
                "AND campaign_id = %s",
                (sim_day, round(new_budget, 2), source, proposal_id, experiment_id, campaign_id))
            self.conn.execute("UPDATE campaigns SET daily_budget = %s WHERE experiment_id = %s "
                              "AND campaign_id = %s",
                              (round(new_budget, 2), experiment_id, campaign_id))

    # ---- runs and proposals ----
    def record_run(self, experiment_id, run):
        (run_id,) = self.conn.execute(
            "INSERT INTO agent_runs (experiment_id, brand_id, sim_day, policy, model, mode, "
            "status, fallback_reason, model_calls, tool_calls, output_retries, api_retries, "
            "input_tokens, output_tokens, latency_ms) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING run_id",
            (experiment_id, run.brand_id, run.sim_day, run.policy, run.model, run.mode,
             run.status, run.fallback_reason, run.model_calls, run.tool_calls,
             run.output_retries, run.api_retries, run.input_tokens, run.output_tokens,
             run.latency_ms)).fetchone()
        run.run_id = run_id
        return run_id

    def list_runs(self, experiment_id):
        rows = self._rows(
            "SELECT brand_id, sim_day, policy, model, mode, status, fallback_reason, "
            "model_calls, tool_calls, output_retries, api_retries, input_tokens, output_tokens, "
            "latency_ms, run_id FROM agent_runs WHERE experiment_id = %s ORDER BY run_id",
            (experiment_id,))
        return [RunRecord(*r) for r in rows]

    def add_proposal(self, experiment_id, p):
        (pid,) = self.conn.execute(
            "INSERT INTO proposals (run_id, experiment_id, brand_id, campaign_id, sim_day, "
            "direction, current_budget, requested_budget, final_budget, reason, "
            "expected_effect, risk, status, guardrails) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING proposal_id",
            (p.run_id, experiment_id, p.brand_id, p.campaign_id, p.sim_day, p.direction,
             p.current_budget, p.requested_budget, p.final_budget, p.reason, p.expected_effect,
             p.risk, p.status, p.guardrails)).fetchone()
        p.proposal_id = pid
        return pid

    _PROPOSAL_SELECT = (
        "SELECT p.run_id, p.brand_id, p.campaign_id, p.sim_day, p.direction, p.current_budget, "
        "p.requested_budget, p.final_budget, p.reason, p.expected_effect, p.risk, p.status, "
        "p.guardrails, p.proposal_id, a.decision, a.reason, a.reviewer, a.rule_id "
        "FROM proposals p LEFT JOIN approvals a USING (proposal_id) ")

    @staticmethod
    def _proposal(r: tuple) -> ProposalRecord:
        return ProposalRecord(r[0], r[1], r[2], r[3], r[4], float(r[5]), float(r[6]),
                              float(r[7]), r[8], r[9], r[10], r[11], list(r[12]), r[13], r[14],
                              r[15], r[16], r[17])

    def get_proposal(self, experiment_id, proposal_id):
        rows = self._rows(self._PROPOSAL_SELECT + "WHERE p.experiment_id = %s "
                          "AND p.proposal_id = %s", (experiment_id, proposal_id))
        if not rows:
            raise StateError(f"unknown proposal {proposal_id}")
        return self._proposal(rows[0])

    def list_proposals(self, experiment_id, status=None, brand_id=None):
        rows = self._rows(
            self._PROPOSAL_SELECT + "WHERE p.experiment_id = %s AND (%s::text IS NULL OR "
            "p.status = %s) AND (%s::text IS NULL OR p.brand_id = %s) ORDER BY p.proposal_id",
            (experiment_id, status, status, brand_id, brand_id))
        return [self._proposal(r) for r in rows]

    def add_guardrail_event(self, experiment_id, sim_day, rule, detail, run_id=None,
                            proposal_id=None, campaign_id=None):
        self.conn.execute(
            "INSERT INTO guardrail_events (experiment_id, run_id, proposal_id, campaign_id, "
            "sim_day, rule, detail) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (experiment_id, run_id, proposal_id, campaign_id, sim_day, rule, detail))

    def list_guardrail_events(self, experiment_id):
        cols = ("experiment_id", "sim_day", "rule", "detail", "run_id", "proposal_id",
                "campaign_id")
        rows = self._rows(f"SELECT {', '.join(cols)} FROM guardrail_events "
                          "WHERE experiment_id = %s ORDER BY event_id", (experiment_id,))
        return [dict(zip(cols, r, strict=True)) for r in rows]

    # ---- decisions: one transaction each ----
    def _lock_pending(self, experiment_id: str, proposal_id: int) -> ProposalRecord:
        rows = self._rows("SELECT status FROM proposals WHERE experiment_id = %s AND "
                          "proposal_id = %s FOR UPDATE", (experiment_id, proposal_id))
        if not rows:
            raise StateError(f"unknown proposal {proposal_id}")
        if rows[0][0] != "pending":
            raise StateError(f"proposal {proposal_id} is {rows[0][0]}, not pending")
        return self.get_proposal(experiment_id, proposal_id)

    def _execute(self, experiment_id: str, p: ProposalRecord) -> None:
        # lock every campaign of the brand so two approvals cannot both pass the cap check
        campaigns = self.list_campaigns(experiment_id, p.brand_id, for_update=True)
        cap = self.get_brand(experiment_id, p.brand_id).daily_budget_cap
        _check_executable(p, campaigns, cap)
        self.set_budget(experiment_id, p.campaign_id, p.sim_day, p.final_budget, "agent",
                        p.proposal_id)

    def decide(self, experiment_id, proposal_id, decision, reviewer, reason, rule_id=None):
        if decision not in ("approve", "reject"):
            raise StateError(f"bad decision {decision!r}")
        with self.conn.transaction():
            p = self._lock_pending(experiment_id, proposal_id)
            if decision == "approve":
                self._execute(experiment_id, p)
            status = "approved" if decision == "approve" else "rejected"
            self.conn.execute("UPDATE proposals SET status = %s, decided_at = now() "
                              "WHERE proposal_id = %s", (status, proposal_id))
            self.conn.execute("INSERT INTO approvals (proposal_id, decision, reviewer, reason, "
                              "rule_id) VALUES (%s, %s, %s, %s, %s)",
                              (proposal_id, decision, reviewer, reason, rule_id))
            self.conn.execute(
                "INSERT INTO decision_memory (experiment_id, brand_id, campaign_id, sim_day, "
                "direction, change_pct, decision, reason, rule_id, proposal_id) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (experiment_id, p.brand_id, p.campaign_id, p.sim_day, p.direction, p.change_pct,
                 decision, reason, rule_id, proposal_id))
            self.log(experiment_id, p.sim_day, f"proposal_{status}",
                     {"proposal_id": proposal_id, "reviewer": reviewer, "reason": reason})
        return self.get_proposal(experiment_id, proposal_id)

    def auto_approve(self, experiment_id, proposal_id):
        with self.conn.transaction():
            p = self._lock_pending(experiment_id, proposal_id)
            self._execute(experiment_id, p)
            self.conn.execute("UPDATE proposals SET status = 'auto_approved', decided_at = now() "
                              "WHERE proposal_id = %s", (proposal_id,))
            self.log(experiment_id, p.sim_day, "proposal_auto_approved",
                     {"proposal_id": proposal_id})
        return self.get_proposal(experiment_id, proposal_id)

    def recall(self, experiment_id, brand_id, before_day, limit=8):
        rows = self._rows(
            "SELECT brand_id, campaign_id, sim_day, direction, change_pct, decision, reason, "
            "rule_id FROM ("
            "  SELECT DISTINCT ON (campaign_id, direction, decision) *"
            "  FROM decision_memory"
            "  WHERE experiment_id = %s AND brand_id = %s AND sim_day < %s"
            "  ORDER BY campaign_id, direction, decision, sim_day DESC, memory_id DESC"
            ") latest ORDER BY (decision = 'reject') DESC, sim_day DESC, memory_id DESC LIMIT %s",
            (experiment_id, brand_id, before_day, limit))
        return [MemoryItem(r[0], r[1], r[2], r[3], float(r[4]), r[5], r[6], r[7]) for r in rows]

    def log(self, experiment_id, sim_day, event, payload):
        self.conn.execute("INSERT INTO decision_log (experiment_id, sim_day, event, payload) "
                          "VALUES (%s, %s, %s, %s::jsonb)",
                          (experiment_id, sim_day, event, json.dumps(payload, default=str)))
