-- 01_clean_events.sql
-- Deduplicate events, fix out-of-order timestamps, label null devices.
--
-- Deduplication rule: an event is a duplicate only if it matches the PREVIOUS
-- event of the same user, event_name and decision_outcome within
-- {{dedup_tolerance_seconds}} seconds. LAG measures the gap to the previous
-- same-type event; only events inside the window are dropped. We never keep
-- "one event per user per type": legitimate KYC retries minutes or hours apart
-- are real behaviour and must survive.

CREATE OR REPLACE TABLE events_dedup AS
WITH ordered AS (
    SELECT
        e.*,
        LAG(event_ts) OVER (
            PARTITION BY user_id, event_name, COALESCE(decision_outcome, '')
            ORDER BY event_ts, event_id
        ) AS prev_same_ts
    FROM raw_events e
)
SELECT
    *,
    date_diff('second', prev_same_ts, event_ts) AS gap_to_prev_same_s,
    COALESCE(date_diff('second', prev_same_ts, event_ts) <= {{dedup_tolerance_seconds}}, FALSE) AS is_duplicate
FROM ordered;

-- Out-of-order: an event logged before the user's first event of the preceding
-- stage (device clock skew). We keep the event (the stage was reached) and
-- correct its timestamp to the preceding stage's first timestamp, flagging it so
-- stage-timing analysis can exclude corrected gaps.
CREATE OR REPLACE TABLE events_clean AS
WITH d AS (
    SELECT
        *,
        CASE event_name
            WHEN 'application_started' THEN 0 WHEN 'kyc_started' THEN 1 WHEN 'kyc_completed' THEN 2
            WHEN 'decision_made' THEN 3 WHEN 'loan_disbursed' THEN 4
        END AS stage
    FROM events_dedup
    WHERE NOT is_duplicate
),
first_ts AS (
    SELECT user_id, stage, MIN(event_ts) AS first_ts
    FROM d
    GROUP BY user_id, stage
)
SELECT
    d.event_id, d.user_id, d.event_name, d.stage, d.decision_outcome,
    d.event_ts AS event_ts_raw,
    GREATEST(d.event_ts, COALESCE(p.first_ts, d.event_ts)) AS event_ts,
    COALESCE(d.event_ts < p.first_ts, FALSE) AS ts_corrected
FROM d
LEFT JOIN first_ts p ON p.user_id = d.user_id AND p.stage = d.stage - 1;

-- Users: null device is a user-agent parsing failure; label it, don't drop the user.
CREATE OR REPLACE TABLE users_clean AS
SELECT
    user_id, signup_ts,
    COALESCE(device, 'unknown') AS device,
    device IS NULL AS device_was_null,
    channel, city_tier, period, variant, assigned_ts,
    CAST(date_trunc('week', signup_ts) AS DATE) AS signup_week
FROM raw_users;
