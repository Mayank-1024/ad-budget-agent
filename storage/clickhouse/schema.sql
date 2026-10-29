-- ClickHouse schema: event-level ad performance (OLAP side).
-- Statements are separated by lines containing only ';' so the Python loader can split them.
--
-- Raw tables are append-only MergeTree tables sorted by (experiment, brand, campaign, time):
-- every agent query filters on experiment + brand (+ campaign) and a time range, so the
-- primary index skips almost all granules. Monthly partitions keep parts small and make
-- dropping old data cheap.

CREATE TABLE IF NOT EXISTS ad_stats_hourly
(
    experiment_id LowCardinality(String),
    brand_id      LowCardinality(String),
    campaign_id   LowCardinality(String),
    channel       LowCardinality(String),
    ts            DateTime('UTC'),
    impressions   UInt32,
    clicks        UInt32,
    spend         Decimal(18, 4)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (experiment_id, brand_id, campaign_id, ts)
;

CREATE TABLE IF NOT EXISTS conversion_events
(
    experiment_id LowCardinality(String),
    brand_id      LowCardinality(String),
    campaign_id   LowCardinality(String),
    channel       LowCardinality(String),
    ts            DateTime('UTC'),
    event_id      UUID,
    order_value   Decimal(18, 4)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (experiment_id, brand_id, campaign_id, ts)
;

-- Daily rollup maintained by the two materialized views below. SummingMergeTree adds up
-- rows with the same sorting key when parts merge in the background, but merges happen
-- whenever ClickHouse decides, so every read must still GROUP BY and sum() (see
-- storage/queries.py). channel is not in the key; it is constant per campaign.
CREATE TABLE IF NOT EXISTS campaign_daily
(
    experiment_id LowCardinality(String),
    brand_id      LowCardinality(String),
    campaign_id   LowCardinality(String),
    channel       LowCardinality(String),
    day           Date,
    impressions   UInt64,
    clicks        UInt64,
    spend         Decimal(18, 4),
    conversions   UInt64,
    revenue       Decimal(18, 4)
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (experiment_id, brand_id, campaign_id, day)
;

-- A materialized view in ClickHouse is an insert trigger: each block inserted into the
-- source table is transformed by the SELECT and written to the target table.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ad_stats_daily TO campaign_daily AS
SELECT
    experiment_id, brand_id, campaign_id, channel,
    toDate(ts) AS day,
    sum(impressions) AS impressions,
    sum(clicks) AS clicks,
    sum(spend) AS spend,
    toUInt64(0) AS conversions,
    toDecimal128(0, 4) AS revenue
FROM ad_stats_hourly
GROUP BY experiment_id, brand_id, campaign_id, channel, day
;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_conversions_daily TO campaign_daily AS
SELECT
    experiment_id, brand_id, campaign_id, channel,
    toDate(ts) AS day,
    toUInt64(0) AS impressions,
    toUInt64(0) AS clicks,
    toDecimal128(0, 4) AS spend,
    count() AS conversions,
    sum(order_value) AS revenue
FROM conversion_events
GROUP BY experiment_id, brand_id, campaign_id, channel, day
;
