-- Postgres schema: agent state (OLTP side). Small, mutable, transactional rows:
-- budgets that change, proposals that move through a status workflow, approvals that
-- must be recorded together with the budget change they cause.
-- Every table carries experiment_id so eval runs (one per policy) never collide.

CREATE TABLE brands (
    experiment_id       text NOT NULL,
    brand_id            text NOT NULL,
    name                text NOT NULL,
    daily_budget_cap    numeric(12, 2) NOT NULL CHECK (daily_budget_cap > 0),
    min_learning_budget numeric(12, 2) NOT NULL CHECK (min_learning_budget >= 0),
    PRIMARY KEY (experiment_id, brand_id)
);

CREATE TABLE campaigns (
    experiment_id text NOT NULL,
    campaign_id   text NOT NULL,
    brand_id      text NOT NULL,
    name          text NOT NULL,
    channel       text NOT NULL,
    objective     text NOT NULL,
    daily_budget  numeric(12, 2) NOT NULL CHECK (daily_budget >= 0),
    PRIMARY KEY (experiment_id, campaign_id),
    FOREIGN KEY (experiment_id, brand_id) REFERENCES brands (experiment_id, brand_id)
        ON DELETE CASCADE
);

CREATE TABLE agent_runs (
    run_id          bigserial PRIMARY KEY,
    experiment_id   text NOT NULL,
    brand_id        text NOT NULL,
    sim_day         date NOT NULL,
    policy          text NOT NULL,
    model           text NOT NULL,
    mode            text NOT NULL CHECK (mode IN ('suggest', 'approve', 'automate')),
    status          text NOT NULL CHECK (status IN ('ok', 'fallback')),
    fallback_reason text,
    model_calls     integer NOT NULL DEFAULT 0,
    tool_calls      integer NOT NULL DEFAULT 0,
    output_retries  integer NOT NULL DEFAULT 0,
    api_retries     integer NOT NULL DEFAULT 0,
    input_tokens    integer,
    output_tokens   integer,
    latency_ms      integer NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (experiment_id, brand_id, sim_day)
);

CREATE TABLE proposals (
    proposal_id      bigserial PRIMARY KEY,
    run_id           bigint NOT NULL REFERENCES agent_runs (run_id) ON DELETE CASCADE,
    experiment_id    text NOT NULL,
    brand_id         text NOT NULL,
    campaign_id      text NOT NULL,
    sim_day          date NOT NULL,
    direction        text NOT NULL CHECK (direction IN ('increase', 'decrease', 'hold')),
    current_budget   numeric(12, 2) NOT NULL,
    requested_budget numeric(12, 2) NOT NULL,
    final_budget     numeric(12, 2) NOT NULL,
    reason           text NOT NULL,
    expected_effect  text NOT NULL,
    risk             text NOT NULL CHECK (risk IN ('low', 'high')),
    status           text NOT NULL CHECK (status IN
                         ('pending', 'approved', 'rejected', 'auto_approved', 'blocked')),
    guardrails       text[] NOT NULL DEFAULT '{}',
    created_at       timestamptz NOT NULL DEFAULT now(),
    decided_at       timestamptz,
    FOREIGN KEY (experiment_id, campaign_id) REFERENCES campaigns (experiment_id, campaign_id)
        ON DELETE CASCADE
);
CREATE INDEX proposals_queue ON proposals (experiment_id, status, sim_day);

CREATE TABLE approvals (
    approval_id bigserial PRIMARY KEY,
    proposal_id bigint NOT NULL UNIQUE REFERENCES proposals (proposal_id) ON DELETE CASCADE,
    decision    text NOT NULL CHECK (decision IN ('approve', 'reject')),
    reviewer    text NOT NULL,
    reason      text NOT NULL,
    rule_id     text,
    decided_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE budget_changes (
    change_id     bigserial PRIMARY KEY,
    experiment_id text NOT NULL,
    campaign_id   text NOT NULL,
    sim_day       date NOT NULL,
    old_budget    numeric(12, 2) NOT NULL,
    new_budget    numeric(12, 2) NOT NULL,
    source        text NOT NULL CHECK (source IN ('agent', 'baseline', 'human')),
    proposal_id   bigint REFERENCES proposals (proposal_id) ON DELETE CASCADE,
    created_at    timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (experiment_id, campaign_id) REFERENCES campaigns (experiment_id, campaign_id)
        ON DELETE CASCADE
);

CREATE TABLE guardrail_events (
    event_id      bigserial PRIMARY KEY,
    experiment_id text NOT NULL,
    run_id        bigint REFERENCES agent_runs (run_id) ON DELETE CASCADE,
    proposal_id   bigint REFERENCES proposals (proposal_id) ON DELETE CASCADE,
    campaign_id   text,
    sim_day       date NOT NULL,
    rule          text NOT NULL,
    detail        text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX guardrail_events_by_exp ON guardrail_events (experiment_id, rule);

-- Memory: one row per reviewer decision, with the reviewer's reason. Retrieved into the
-- next proposal's prompt (see StateStore.recall).
CREATE TABLE decision_memory (
    memory_id     bigserial PRIMARY KEY,
    experiment_id text NOT NULL,
    brand_id      text NOT NULL,
    campaign_id   text NOT NULL,
    sim_day       date NOT NULL,
    direction     text NOT NULL,
    change_pct    numeric(8, 2) NOT NULL,
    decision      text NOT NULL CHECK (decision IN ('approve', 'reject')),
    reason        text NOT NULL,
    rule_id       text,
    proposal_id   bigint REFERENCES proposals (proposal_id) ON DELETE CASCADE
);
CREATE INDEX decision_memory_recall ON decision_memory (experiment_id, brand_id, sim_day DESC);

-- Append-only audit trail of everything that happened, in order.
CREATE TABLE decision_log (
    log_id        bigserial PRIMARY KEY,
    experiment_id text NOT NULL,
    sim_day       date NOT NULL,
    event         text NOT NULL,
    payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX decision_log_by_exp ON decision_log (experiment_id, log_id);
