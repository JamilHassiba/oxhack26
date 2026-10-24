-- migrate: no-transaction
-- Call statistics for the Analytics page: a Tiger Data continuous aggregate over the call_events
-- hypertable. Owner: Alex. Read by GET /analytics/summary (backend/app/routers/analytics.py).
--
-- One row per call per hour. TimescaleDB keeps it up to date with a refresh policy, and
-- materialized_only = false adds events newer than the last refresh on the fly, so the page is
-- always current. Continuous aggregates can't be created inside a transaction (first line).

CREATE MATERIALIZED VIEW IF NOT EXISTS call_stats_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket(INTERVAL '1 hour', ts) AS bucket,
    call_id,
    min(ts) AS first_event_at,
    count(*) FILTER (WHERE kind = 'transcript_line') AS transcript_lines,
    bool_or(kind = 'ended') AS ended,
    max((payload->>'duration_seconds')::numeric) FILTER (WHERE kind = 'ended') AS duration_seconds
FROM call_events
GROUP BY bucket, call_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('call_stats_hourly',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => true);
