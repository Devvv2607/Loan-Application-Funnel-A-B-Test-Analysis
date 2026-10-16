-- 04_funnel_segments.sql
-- The same funnel by device, channel, city tier and signup week (pre-period).
-- LAG gives stage-to-stage conversion within a segment, SUM() OVER the
-- segment's drop-off shares, and RANK() the worst transition per segment.

CREATE OR REPLACE TABLE funnel_segments AS
WITH long AS (
    SELECT dim, segment, stage, users FROM (
        SELECT dim, segment,
               SUM(reached_application_started::INT) AS application_started,
               SUM(reached_kyc_started::INT)         AS kyc_started,
               SUM(reached_kyc_completed::INT)       AS kyc_completed,
               SUM(reached_decision_made::INT)       AS decision_made,
               SUM(reached_loan_disbursed::INT)      AS loan_disbursed
        FROM (
            SELECT 'device' AS dim, device AS segment, * FROM user_stage_flags WHERE period = 'pre'
            UNION ALL SELECT 'channel', channel, * FROM user_stage_flags WHERE period = 'pre'
            UNION ALL SELECT 'city_tier', city_tier, * FROM user_stage_flags WHERE period = 'pre'
            UNION ALL SELECT 'week', strftime(signup_week, '%Y-%m-%d'), * FROM user_stage_flags WHERE period = 'pre'
        )
        GROUP BY dim, segment
    ) UNPIVOT (users FOR stage IN (application_started, kyc_started, kyc_completed, decision_made, loan_disbursed))
),
ordered AS (
    SELECT *,
        CASE stage WHEN 'application_started' THEN 1 WHEN 'kyc_started' THEN 2 WHEN 'kyc_completed' THEN 3
                   WHEN 'decision_made' THEN 4 WHEN 'loan_disbursed' THEN 5 END AS stage_order
    FROM long
),
steps AS (
    SELECT *,
        LAG(users) OVER w AS prev_users,
        LAG(users) OVER w - users AS dropped
    FROM ordered
    WINDOW w AS (PARTITION BY dim, segment ORDER BY stage_order)
)
SELECT
    dim, segment, stage_order, stage, users, prev_users, dropped,
    users::DOUBLE / prev_users AS conversion_from_prev,
    dropped::DOUBLE / SUM(dropped) OVER (PARTITION BY dim, segment) AS dropoff_share,
    CASE WHEN dropped IS NOT NULL
         THEN RANK() OVER (PARTITION BY dim, segment ORDER BY dropped DESC NULLS LAST) END AS dropoff_rank
FROM steps
ORDER BY dim, segment, stage_order;

-- Cube for the interactive funnel explorer: stage counts for every
-- device x channel x tier x week cell, so any filter combination is an exact sum.
CREATE OR REPLACE TABLE funnel_cube AS
SELECT
    device, channel, city_tier, strftime(signup_week, '%Y-%m-%d') AS week,
    SUM(reached_application_started::INT) AS application_started,
    SUM(reached_kyc_started::INT)         AS kyc_started,
    SUM(reached_kyc_completed::INT)       AS kyc_completed,
    SUM(reached_decision_made::INT)       AS decision_made,
    SUM(reached_loan_disbursed::INT)      AS loan_disbursed
FROM user_stage_flags
WHERE period = 'pre'
GROUP BY ALL
ORDER BY ALL;
