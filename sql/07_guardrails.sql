-- 07_guardrails.sql
-- Guardrail numerators and denominators per arm.
--   (a) DECISION: early-delinquent loans per randomized user. Denominator is
--       everyone randomized, so the comparison is still randomized and captures
--       the selection effect (more, and different, borrowers).
--   (b) DIAGNOSTIC: early delinquency rate among disbursed loans. The
--       denominator is post-randomization (who got a loan), so the arms hold
--       different borrower mixes; it describes composition, not causal harm.
--   (c) DIAGNOSTIC: approval rate among credit decisions (same caveat).

CREATE OR REPLACE TABLE guardrail_inputs AS
SELECT variant, 'delinquent_per_1000_randomized' AS guardrail,
       SUM(early_delinquent::INT) AS numerator, COUNT(*) AS denominator
FROM experiment_users GROUP BY variant
UNION ALL
SELECT variant, 'early_delinquency_rate', SUM(early_delinquent::INT), SUM(disbursed::INT)
FROM experiment_users GROUP BY variant
UNION ALL
SELECT variant, 'approval_rate', SUM(approved::INT), SUM(decision_made::INT)
FROM experiment_users GROUP BY variant
ORDER BY guardrail, variant;
