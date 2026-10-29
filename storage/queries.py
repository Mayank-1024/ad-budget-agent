"""Every ClickHouse query the system runs. All are parameterized.

The model never writes SQL. Tool calls carry typed arguments (a window length, a campaign
id that code has already checked belongs to the brand) and code binds them as server-side
parameters with ClickHouse's `{name:Type}` syntax, so a value can never change the query.

Reads go to `campaign_daily` (the materialized-view rollup). Because SummingMergeTree
collapses rows only when parts merge, each query groups and sums again.
"""

WINDOW_METRICS = """
SELECT
    campaign_id,
    uniqExact(day)                          AS days_with_data,
    toFloat64(sum(spend))                   AS total_spend,
    sum(impressions)                        AS total_impressions,
    sum(clicks)                             AS total_clicks,
    sum(conversions)                        AS total_conversions,
    toFloat64(sum(revenue))                 AS total_revenue
FROM campaign_daily
WHERE experiment_id = {experiment_id:String}
  AND brand_id = {brand_id:String}
  AND day BETWEEN {start_day:Date} AND {end_day:Date}
GROUP BY campaign_id
ORDER BY campaign_id
"""

DAILY_SERIES = """
SELECT
    day,
    toFloat64(sum(spend))   AS total_spend,
    sum(impressions)        AS total_impressions,
    sum(clicks)             AS total_clicks,
    sum(conversions)        AS total_conversions,
    toFloat64(sum(revenue)) AS total_revenue
FROM campaign_daily
WHERE experiment_id = {experiment_id:String}
  AND campaign_id = {campaign_id:String}
  AND day BETWEEN {start_day:Date} AND {end_day:Date}
GROUP BY day
ORDER BY day
"""

# Reads the raw event tables directly (no rollup): conversions per day next to clicks per
# day, used to cross-check the materialized view in integration tests.
RAW_DAILY_CHECK = """
SELECT s.day, s.clicks, coalesce(c.conversions, 0) AS conversions
FROM
(
    SELECT toDate(ts) AS day, sum(clicks) AS clicks
    FROM ad_stats_hourly
    WHERE experiment_id = {experiment_id:String} AND campaign_id = {campaign_id:String}
    GROUP BY day
) AS s
LEFT JOIN
(
    SELECT toDate(ts) AS day, count() AS conversions
    FROM conversion_events
    WHERE experiment_id = {experiment_id:String} AND campaign_id = {campaign_id:String}
    GROUP BY day
) AS c ON s.day = c.day
ORDER BY s.day
SETTINGS join_use_nulls = 1
"""
