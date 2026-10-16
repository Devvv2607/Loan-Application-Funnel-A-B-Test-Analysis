-- 02_user_stage_flags.sql
-- One row per user: first timestamp and a strict funnel flag for every stage.
--
-- Funnel logic: a user counts at a stage only if they reached every earlier
-- stage. Users with a later-stage event but a missing preceding stage (a logging
-- gap) are excluded from the later stages and reported, not silently promoted.

CREATE OR REPLACE TABLE user_stage_flags AS
WITH firsts AS (
    SELECT
        user_id,
        MIN(event_ts) FILTER (WHERE stage = 0) AS application_started_ts,
        MIN(event_ts) FILTER (WHERE stage = 1) AS kyc_started_ts,
        MIN(event_ts) FILTER (WHERE stage = 2) AS kyc_completed_ts,
        MIN(event_ts) FILTER (WHERE stage = 3) AS decision_made_ts,
        MIN(event_ts) FILTER (WHERE stage = 4) AS loan_disbursed_ts,
        COUNT(*) FILTER (WHERE stage = 1) AS kyc_started_events,
        BOOL_OR(decision_outcome = 'approved') AS approved_any,
        BOOL_OR(ts_corrected) AS any_ts_corrected
    FROM events_clean
    GROUP BY user_id
),
flags AS (
    SELECT
        u.user_id, u.period, u.device, u.channel, u.city_tier, u.signup_week, u.variant, u.assigned_ts,
        f.application_started_ts, f.kyc_started_ts, f.kyc_completed_ts, f.decision_made_ts, f.loan_disbursed_ts,
        COALESCE(f.kyc_started_events, 0) AS kyc_started_events,
        COALESCE(f.any_ts_corrected, FALSE) AS any_ts_corrected,
        f.application_started_ts IS NOT NULL AS has_application,
        f.kyc_started_ts IS NOT NULL AS has_kyc_started,
        f.kyc_completed_ts IS NOT NULL AS has_kyc_completed,
        f.decision_made_ts IS NOT NULL AS has_decision,
        COALESCE(f.approved_any, FALSE) AS has_approval,
        f.loan_disbursed_ts IS NOT NULL AS has_disbursal
    FROM users_clean u
    LEFT JOIN firsts f USING (user_id)
)
SELECT
    flags.*,
    has_application AS reached_application_started,
    has_application AND has_kyc_started AS reached_kyc_started,
    has_application AND has_kyc_started AND has_kyc_completed AS reached_kyc_completed,
    has_application AND has_kyc_started AND has_kyc_completed AND has_decision AS reached_decision_made,
    has_application AND has_kyc_started AND has_kyc_completed AND has_decision AND has_approval
        AND has_disbursal AS reached_loan_disbursed,
    -- Excluded for a missing step: has some later-stage event that strict logic does not count.
    (has_kyc_completed AND NOT (has_application AND has_kyc_started))
        OR (has_decision AND NOT (has_application AND has_kyc_started AND has_kyc_completed))
        OR (has_disbursal AND NOT (has_application AND has_kyc_started AND has_kyc_completed AND has_decision))
        AS excluded_missing_step,
    l.loan_id, l.amount AS loan_amount, l.dpd_30_on_first_emi
FROM flags
LEFT JOIN raw_loans l USING (user_id);
