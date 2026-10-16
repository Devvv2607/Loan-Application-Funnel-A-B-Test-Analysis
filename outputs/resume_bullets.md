# Resume bullet drafts (simulated-data project)

> All figures come from a simulated dataset with planted effects (fictional lender). Say so on the resume.

- Built an end-to-end SQL (DuckDB) funnel analysis on a simulated loan event log (25,095 pre-period applicants); identified KYC as the largest drop-off (42% of all drop-off).
- Pre-registered and analysed a simulated A/B test of a simplified KYC flow: +4.5 pp KYC completion (95% CI 3.1–6.0 pp), recovering the planted true effect inside the CI.
- Designed a break-even non-inferiority guardrail on early-delinquent loans per 1,000 users; result inconclusive (bound +4.6 vs +2.1), leading to a pre-registered "Iterate" call instead of an unsupported ship.
- Validated the method by simulation: A/A false-positive rate 4.9%, CI coverage 95.4%, SRM detection of a broken split, and a peeking demo (25% vs 5% false positives).

Source claims: DEC-001, EXP-001, EXP-002, EXP-003, EXP-004, EXP-005, FUN-001, FUN-002, FUN-003, FUN-004, GRD-001, GRD-002, GRD-003, PWR-001, PWR-002, VAL-001, VAL-002, VAL-003, VAL-004, VAL-005
