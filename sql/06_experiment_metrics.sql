-- 06_experiment_metrics.sql
-- Intention-to-treat experiment tables.
--
-- Population: every user randomized at KYC start (variant from the assignment
-- log). The assignment record itself proves KYC entry, so users whose
-- kyc_started event was lost in logging still count. Every metric's denominator
-- is ALL randomized users in the arm; outcomes after randomization (abandoning
-- KYC, being declined) only ever set a numerator flag to 0, never remove a user.

CREATE OR REPLACE TABLE experiment_users AS
SELECT
    user_id, variant, assigned_ts,
    CAST(assigned_ts AS DATE) AS assigned_date,
    device, channel, city_tier,
    has_kyc_completed AS kyc_completed,
    has_kyc_completed AND has_decision AS decision_made,
    has_kyc_completed AND has_decision AND has_approval AS approved,
    has_kyc_completed AND has_decision AND has_approval AND has_disbursal AS disbursed,
    has_kyc_completed AND has_decision AND has_approval AND has_disbursal
        AND COALESCE(dpd_30_on_first_emi, 0) = 1 AS early_delinquent
FROM user_stage_flags
WHERE variant IS NOT NULL;

CREATE OR REPLACE TABLE experiment_arm_metrics AS
SELECT
    variant,
    COUNT(*)                              AS randomized,
    SUM(kyc_completed::INT)               AS kyc_completed,
    SUM(decision_made::INT)               AS decisions,
    SUM(approved::INT)                    AS approvals,
    SUM(disbursed::INT)                   AS disbursed,
    SUM(early_delinquent::INT)            AS early_delinquent
FROM experiment_users
GROUP BY variant
ORDER BY variant;

-- Cumulative counts by assignment day (for the "don't peek" chart).
CREATE OR REPLACE TABLE experiment_daily AS
WITH daily AS (
    SELECT assigned_date, variant, COUNT(*) AS randomized, SUM(kyc_completed::INT) AS kyc_completed
    FROM experiment_users GROUP BY ALL
)
SELECT
    assigned_date, variant,
    SUM(randomized) OVER w AS cum_randomized,
    SUM(kyc_completed) OVER w AS cum_kyc_completed
FROM daily
WINDOW w AS (PARTITION BY variant ORDER BY assigned_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
ORDER BY assigned_date, variant;
