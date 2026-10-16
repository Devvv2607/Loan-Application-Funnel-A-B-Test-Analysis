-- 05_stage_timing.sql
-- Median and p90 minutes between consecutive stages (first timestamps),
-- overall and by device, pre-period. Users with a corrected out-of-order
-- timestamp are excluded: their gaps are artefacts of the correction.

CREATE OR REPLACE TABLE stage_timing AS
WITH gaps AS (
    SELECT device, transition, minutes FROM (
        SELECT device,
            date_diff('second', application_started_ts, kyc_started_ts) / 60.0 AS "application_started→kyc_started",
            date_diff('second', kyc_started_ts, kyc_completed_ts) / 60.0       AS "kyc_started→kyc_completed",
            date_diff('second', kyc_completed_ts, decision_made_ts) / 60.0     AS "kyc_completed→decision_made",
            date_diff('second', decision_made_ts, loan_disbursed_ts) / 60.0    AS "decision_made→loan_disbursed"
        FROM user_stage_flags
        WHERE period = 'pre' AND NOT any_ts_corrected AND NOT excluded_missing_step
    ) UNPIVOT (minutes FOR transition IN ("application_started→kyc_started", "kyc_started→kyc_completed",
                                          "kyc_completed→decision_made", "decision_made→loan_disbursed"))
)
SELECT 'all' AS device, transition, COUNT(*) AS users,
       quantile_cont(minutes, 0.5) AS median_minutes, quantile_cont(minutes, 0.9) AS p90_minutes
FROM gaps GROUP BY transition
UNION ALL
SELECT device, transition, COUNT(*), quantile_cont(minutes, 0.5), quantile_cont(minutes, 0.9)
FROM gaps GROUP BY device, transition
ORDER BY device, transition;
