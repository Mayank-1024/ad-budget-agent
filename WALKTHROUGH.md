# Walkthrough (interview prep)

This file is for explaining the project out loud: what each file does, why it is built
that way, and the questions an interviewer is likely to ask, with honest answers. The
numbers quoted here come from the runs recorded in the README.

## The one-minute version

Converge-style budget agents read performance data, propose budget moves, and a human
approves before anything executes. This project builds that loop end to end on synthetic
data:

1. A simulator generates event-level ad data for 3 invented brands and 11 campaigns, with
   hidden response curves (diminishing returns, a fatiguing creative, a promo week, an
   attribution gap, and a campaign whose tracking breaks).
2. The events go into **ClickHouse** (MergeTree tables, a materialized-view daily rollup).
3. Each simulated morning, **Claude** reads metrics through two tools that run fixed,
   parameterized ClickHouse queries, and returns a strict JSON proposal.
4. **Code** validates the proposal, then enforces budget guardrails (max 20% per day,
   brand cap, learning floor, tracking freeze).
5. Proposals go into **Postgres**, through an approval mode (suggest / approve /
   automate). A simulated reviewer (or a person in the dashboard) approves or rejects
   with a reason. Approved moves execute in the same transaction.
6. Reviewer decisions are **memory**: the next day's prompt includes the relevant past
   decisions.
7. **Evals** score the agent against a hold baseline and a ROAS rule on the hidden ground
   truth, and measure whether memory reduces repeated rejected proposals.

## File by file

| Path | What it does | What to be able to say |
|---|---|---|
| `sim/scenario.py` | Brands, campaigns, and their hidden parameters | Which campaign hides which trap, and why each trap exists |
| `sim/market.py` | Turns budgets into hourly stats + conversion events + ground truth | Concave curve `max_conv * (1 - exp(-spend/sat))`; Poisson noise; one RNG per (seed, campaign, day) so policies are compared on the same luck |
| `storage/clickhouse/schema.sql` | Raw MergeTree tables, `campaign_daily` SummingMergeTree, two materialized views | ORDER BY choice, partitions, why reads still `GROUP BY` |
| `storage/queries.py` | Every ClickHouse query, parameterized with `{name:Type}` | The model never writes SQL |
| `storage/events.py` | `ClickHouseEventStore` and an in-memory twin | Ratios computed from sums; the twin keeps unit tests Docker-free and is checked against ClickHouse in an integration test |
| `storage/postgres/migrations/001_init.sql` | OLTP schema: brands, campaigns, agent_runs, proposals, approvals, budget_changes, guardrail_events, decision_memory, decision_log | CHECK constraints for statuses, FKs with cascade, `experiment_id` everywhere |
| `storage/state.py` | `PostgresStateStore` and an in-memory twin | `decide` is one transaction: lock, stale check, cap check, update, approval row, memory row, audit row |
| `agent/tools.py` | Two tools, `strict: true`, brand bound from context | Why the brand is not a tool argument |
| `agent/prompts.py` | Static system prompt, per-day user message with `<reviewer_memory>` | Static system prompt so it is cache-friendly and reproducible |
| `agent/proposal.py` | Pydantic schema + semantic checks | Schema (shape) vs semantics (ids, action matches budget) |
| `agent/loop.py` | Tool loop, one validation retry, tool budget, fallback to hold | Every failure ends in "hold all budgets" |
| `agent/anthropic_model.py` | Messages API call with tools + `output_config.format` | SDK retries off (the loop owns retries); error classification; thinking blocks passed back verbatim |
| `agent/guardrails.py` | The four budget rules, fixed order | Why order matters (freeze before clip, cap last) |
| `agent/scripted_model.py` | `ScriptedModel` (replay) and `RulePlayingModel` (a fixed rule through the real loop) | Offline tests exercise the real pipeline; these are not models |
| `approvals/policy.py` | Modes and the low-risk rule (<=10% change, no guardrail fired, not an increase on a flagged campaign) | Why auto-approve thresholds live in code |
| `approvals/reviewer.py` | Simulated reviewer with knowledge the agent lacks | Its rules are right on the hidden ground truth |
| `engine/cycle.py` | One brand-day: propose, guard, store, approve, execute | Decreases execute before increases |
| `engine/simulation.py` | Warm-up, then daily loop; truth kept out of the databases | Ground truth never reaches anything the agent can read |
| `evals/metrics.py`, `evals/run.py`, `evals/rescore.py` | Scoring, the CLI with a hard spend guard, and re-scoring a window from Postgres | Expected true revenue as the headline metric, and why |
| `api/main.py`, `web/` | Approval queue API and React dashboard | Human decisions go through the same `decide` as the simulated reviewer |
| `tests/` | Unit tests (offline) and `-m db` integration tests | What each layer's tests prove |

## Design decisions and why

**ClickHouse for events, Postgres for state.** The two workloads are different. Event
data is append-only, large, and read as aggregates over time ranges: that is what a
columnar store with sorted, compressed parts is built for. Agent state is small, mutable,
and needs transactions: approving a proposal must update the budget, write the approval,
and write memory atomically, and two approvals must not both pass the cap check. That is
what Postgres row locks and transactions are for. ClickHouse has no multi-statement
transactions, and Postgres would be wasteful for scanning millions of event rows.

**The model never writes SQL.** Tools take a window length from a fixed enum and a
campaign id. Code checks the id belongs to the brand in context and binds values as
server-side parameters. The brand is not a tool argument at all, so a run cannot read
another brand's data whatever the model sends.

**Guardrails are code, not prompt.** The prompt tells the model the limits so it wastes
fewer moves, but `apply_guardrails` is what enforces them, and it runs on every policy,
including the baselines. A clipped or blocked move is recorded in `guardrail_events` with
the requested and final budget, so the dashboard shows "asked $1,248, got $1,098".

**Validation vs guardrails.** An unknown campaign id or "increase" with a lower budget is
an invalid answer, so the model gets one retry with the exact error. A move that is valid
but too big is not an error; it is clipped. Mixing the two would either retry on things
code can fix, or silently "fix" answers that are actually confused.

**Fallback is "hold".** If the model fails twice, times out, or refuses, nothing changes.
For a budget agent the safe default is the status quo, not an emergency action.

**Tracking freeze holds in both directions.** Zero conversions with normal clicks reads
as ROAS 0, which is exactly what would make an optimizer cut a campaign that may be
working fine. In the simulator it is working fine (true conversions continue). So the
guardrail blocks cuts as well as increases until a person looks.

**Memory is structured retrieval in SQL, not embeddings.** The relevant past decisions
for a brand are easy to define exactly: the latest decision per (campaign, direction,
decision), rejections first, newest first, at most 8, only from earlier days.
`DISTINCT ON` does it in one query. Embeddings would add a model, a vector index and
fuzziness for no gain at this size. With free-text notes from many reviewers, semantic
search would start to earn its place.

**Expected true revenue as the headline metric.** Realized revenue includes Poisson
noise, so two policies can differ by luck. The expected value of the true response curve
at the spend each policy chose removes that, and it counts the sales the platforms did
not report (attribution gap, broken pixel), which is the point: the agent only sees
reported numbers, and is judged on reality.

**Common random numbers.** Each (seed, campaign, day) has its own RNG, so if two policies
set the same budget for a campaign on a day, they get identical outcomes. Differences
between policies then come from decisions, not from noise.

**Offline first.** `ScriptedModel` replays fixed traces (including bad ones) and
`RulePlayingModel` plays a rule through the real tool loop. With the in-memory stores,
`pytest` needs no key and no Docker. The integration tests then check the in-memory
stores against ClickHouse and Postgres, including one test that runs a whole short
experiment on both and asserts identical scores.

## ClickHouse basics to be able to explain

- **Columnar storage.** Each column is stored (and compressed) separately, so a query
  that sums `spend` over a date range reads only `spend`, `day` and the filter columns,
  not whole rows. That is why it is fast for analytics and poor for point updates.
- **MergeTree and parts.** Every insert writes an immutable sorted "part". Background
  merges combine parts. Insert in batches (here: one insert per table per simulated
  day), not row by row, or you create too many small parts.
- **ORDER BY is the primary index.** Data in each part is sorted by the ORDER BY key and
  ClickHouse keeps a sparse index (one entry per granule, 8,192 rows by default). Filters
  on a prefix of the key skip granules. Here the key is
  `(experiment_id, brand_id, campaign_id, ts)` because every query filters on experiment
  and brand (and often campaign) plus a time range.
- **PARTITION BY.** Monthly partitions (`toYYYYMM(ts)`) keep parts manageable and make
  retention cheap (drop a partition). Partitions are not an index; do not over-partition.
- **LowCardinality(String).** Dictionary-encodes columns with few distinct values (ids,
  channel), which saves space and speeds up filters and GROUP BY.
- **Materialized views are insert triggers.** `mv_ad_stats_daily` runs its SELECT on each
  block inserted into `ad_stats_hourly` and writes the result into `campaign_daily`. It
  does not see rows inserted before it was created, and it does not re-run on updates.
- **SummingMergeTree is eventually collapsed.** Rows with the same ORDER BY key are summed
  when parts merge, but merges happen whenever ClickHouse decides. Until then there can be
  several rows per (campaign, day), so every read must still `GROUP BY` and `sum()`.
  Querying it without GROUP BY gives wrong (partial) numbers. `FINAL` forces collapsing
  at read time but is slower.
- **Mutations are heavy.** `ALTER TABLE ... DELETE` rewrites parts asynchronously. It is
  used here only to reset an eval experiment, with `mutations_sync = 2` so tests can
  rely on it. In production you would use TTLs or drop partitions instead.
- **Parameterized queries.** `{brand_id:String}` placeholders are bound server-side by
  ClickHouse, so a value cannot change the query structure.
- **Decimal for money.** Spend and order values are `Decimal(18, 4)`, cast to Float64
  only in the final SELECT.

## Postgres pieces to be able to explain

- `SELECT ... FOR UPDATE` on the proposal and on all of the brand's campaign rows inside
  `decide`, so two concurrent approvals serialize and the cap check sees the real total.
- The stale check: a proposal stores the budget it was made against; if the budget has
  changed since, approval is refused (optimistic concurrency).
- `DISTINCT ON (campaign_id, direction, decision) ... ORDER BY ..., sim_day DESC` for
  "latest decision per key" in memory recall.
- CHECK constraints for every status column, foreign keys with `ON DELETE CASCADE`, and a
  migration runner that takes an advisory lock and records applied versions.

## Likely interview questions, with honest answers

**1. Why two databases? Isn't that over-engineering for a demo?**
At demo size Postgres alone would work. The split is about the shapes of the workloads:
append-only, aggregate-heavy event data versus small transactional state. Converge runs
both for this reason. I wanted to show I know which belongs where and what each costs:
ClickHouse gives fast aggregates but no transactions and eventual rollups; Postgres gives
transactions and constraints but is the wrong tool for scanning event history.

**2. Walk me through what happens when Claude proposes +35% on a campaign.**
The proposal passes validation (valid id, increase with a higher budget). The guardrail
clips it to +20% and records a `max_change` event with requested and final budgets. Risk
is "high" because a guardrail fired, so even in automate mode it goes to the reviewer. If
approved, `decide` locks the brand's campaign rows, checks the proposal is not stale and
the cap still holds, updates the budget, and writes the approval, memory and audit rows
in one transaction.

**3. How do you stop the model from doing something dangerous?**
It cannot act. It can only return JSON. It cannot write SQL. It cannot read another
brand. Its output is validated, then clipped by code, then (by default) approved by a
person before anything executes. Failures fall back to holding budgets.

**4. How do you know the agent is good?**
Evals against two baselines on hidden ground truth. Over the full 21 eval days and two
seeds (run 2026-10-29 to 30), every agent variant beat holding budgets by 9.2% to 11.2% on
net after ad spend and beat the ROAS rule, which lost money relative to holding because it cut the
under-reported prospecting campaign and scaled saturated brand search. The honest caveat: I designed the simulator, so the agent
is being tested on traps I chose. It shows the loop works and the measurement is set up
correctly, not that the agent would beat a media buyer on real accounts.

**5. What does the reviewer memory actually buy you?**
In approve mode, a rejected move never executes, so memory does not change revenue much;
what it changes is reviewer workload: how many times a person has to say "no" to the same
thing. The eval counts repeated rejections (same campaign, direction and rule as an
earlier rejection) with and without memory: 44 and 41 without, 0 and 0 with, over 21 days
on the two seeds, and the memory agent proposed about half as many moves. Memory did not
clearly change revenue: net was 1.6% higher with memory in one seed and 0.3% lower in the
other. Two seeds cannot tell whether a difference that small is real. In automate mode, where small moves skip the reviewer,
memory could matter for outcomes too; that is the next experiment.

**6. What happens when the model returns garbage or the API is down?**
Invalid JSON or a semantic error gets one retry with the exact error message. A second
failure, exhausted API retries, a refusal, or asking for tools after the tool budget is
spent all end in the same fallback: hold every budget and record the run as a fallback
with its reason.

**7. Explain SummingMergeTree and what goes wrong if you forget GROUP BY.**
See the ClickHouse section: rows are summed only when parts merge, so a read without
GROUP BY can return several partial rows for one campaign-day. The integration test
compares the rollup with the raw event tables to catch exactly this kind of mistake.

**8. What would change at Converge scale ($1M+ per day, many brands)?**
Runs would be queued and parallel per brand (a worker pool like the Celery setup in my
commerce agent), with per-tenant quotas and spend tracking. ClickHouse would be a
cluster with replicated tables, ingest from platform APIs in batches, and rollups at
several grains. The real hard problems are measurement ones the simulator only hints at:
attribution windows and lag, incrementality (is the campaign causing sales or taking
credit), and learning-phase resets on the ad platforms when budgets move too fast.

**9. What did the first real run teach you?**
The first real run hit the tool-step limit: Claude asked for the daily trend of several
campaigns in one parallel batch and overshot 6 calls, so those runs fell back to holding.
That was my limit being too tight and too abrupt, not the model misbehaving. I raised it
to 10 and made it graceful (the batch is not run, the model is told the budget is used up
and answers with what it has), and added tests for both paths. Second, the API account ran out of
credit mid-run: every later call returned HTTP 400 and every run fell back to holding
budgets, exactly as designed. I scored the 8 days before that by rebuilding them from
Postgres and re-running the deterministic market, and checked the re-scorer reproduces a
complete run's report exactly before trusting it. After a top-up I reran all five
experiments for the full 21 days under new tags, so the 8-day results stayed intact; the
gain over holding grew to 9.2% to 11.2%. The full runs also showed the agent leaving the
broken-tracking campaign alone, and not clearly reacting to the promo week, which is the
next thing to examine.

**10. How much of this did you write vs Claude Code?**
Answer this honestly in your own words. The README credit says it was built with Claude
Code. Be ready to explain every design decision above, to change a guardrail or a query
live, and to say what you would do differently.
