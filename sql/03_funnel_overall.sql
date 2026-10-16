-- 03_funnel_overall.sql
-- Pre-period funnel: users at each stage, stage-to-stage conversion, each
-- transition's share of total drop-off, and conversion from application start.
-- Strict flags from 02 guarantee counts are non-increasing.

CREATE OR REPLACE TABLE funnel_overall AS
WITH counts AS (
    SELECT * FROM (
        SELECT
            SUM(reached_application_started::INT) AS application_started,
            SUM(reached_kyc_started::INT)         AS kyc_started,
            SUM(reached_kyc_completed::INT)       AS kyc_completed,
            SUM(reached_decision_made::INT)       AS decision_made,
            SUM(reached_loan_disbursed::INT)      AS loan_disbursed
        FROM user_stage_flags
        WHERE period = 'pre'
    ) UNPIVOT (users FOR stage IN (application_started, kyc_started, kyc_completed, decision_made, loan_disbursed))
),
ordered AS (
    SELECT
        CASE stage WHEN 'application_started' THEN 1 WHEN 'kyc_started' THEN 2 WHEN 'kyc_completed' THEN 3
                   WHEN 'decision_made' THEN 4 WHEN 'loan_disbursed' THEN 5 END AS stage_order,
        stage, users
    FROM counts
),
steps AS (
    SELECT
        stage_order, stage, users,
        LAG(users) OVER (ORDER BY stage_order) AS prev_users,
        LAG(users) OVER (ORDER BY stage_order) - users AS dropped,
        FIRST_VALUE(users) OVER (ORDER BY stage_order) AS start_users
    FROM ordered
)
SELECT
    stage_order, stage, users, prev_users, dropped,
    users::DOUBLE / prev_users AS conversion_from_prev,
    dropped::DOUBLE / SUM(dropped) OVER () AS dropoff_share,
    users::DOUBLE / start_users AS conversion_from_start
FROM steps
ORDER BY stage_order;
