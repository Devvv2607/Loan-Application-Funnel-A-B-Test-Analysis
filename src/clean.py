"""Phase 2b: run the cleaning SQL and write the data-quality report.

The report keeps injected and detected counts side by side, so the cleaning step
is checked against what the generator actually planted rather than trusted.
"""

from __future__ import annotations

from common import ROOT, read_json, settings, write_json
from ingest import connect


def run_sql(con, name: str, **params) -> None:
    sql = (ROOT / settings()["paths"]["sql"] / name).read_text(encoding="utf-8")
    for k, v in params.items():
        sql = sql.replace("{{" + k + "}}", str(v))
    con.execute(sql)


def main() -> None:
    s = settings()
    tol = s["cleaning"]["dedup_tolerance_seconds"]
    con = connect()
    run_sql(con, "01_clean_events.sql", dedup_tolerance_seconds=tol)
    run_sql(con, "02_user_stage_flags.sql")

    q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    inj = read_json("outputs/injected_issues.json")
    detected_dups = q("SELECT COUNT(*) FROM events_dedup WHERE is_duplicate")
    repeats_kept = q("""SELECT COALESCE(SUM(n - 1), 0) FROM (
                          SELECT user_id, event_name, COUNT(*) AS n FROM events_clean
                          GROUP BY user_id, event_name HAVING COUNT(*) > 1)""")
    repeats_by_event = dict(con.execute("""SELECT event_name, SUM(n - 1) FROM (
                          SELECT user_id, event_name, COUNT(*) AS n FROM events_clean
                          GROUP BY user_id, event_name HAVING COUNT(*) > 1) GROUP BY 1 ORDER BY 1""").fetchall())
    ooo = q("SELECT COUNT(*) FROM events_clean WHERE ts_corrected")
    ooo_by = dict(con.execute("SELECT event_name, COUNT(*) FROM events_clean WHERE ts_corrected "
                              "GROUP BY 1 ORDER BY 1").fetchall())
    null_dev = q("SELECT COUNT(*) FROM users_clean WHERE device_was_null")
    missing = q("SELECT COUNT(*) FROM user_stage_flags WHERE excluded_missing_step")
    # Anything still inconsistent after the rules above is reported, not hidden.
    unresolved = {
        "events_for_unknown_users": q("SELECT COUNT(*) FROM events_clean e "
                                      "ANTI JOIN users_clean u USING (user_id)"),
        "loans_without_disbursal_event": q("SELECT COUNT(*) FROM raw_loans l ANTI JOIN "
                                           "(SELECT user_id FROM events_clean WHERE stage = 4) e USING (user_id)"),
    }
    handled = {
        "randomized_users_without_kyc_started_event": {
            "count": q("SELECT COUNT(*) FROM user_stage_flags WHERE variant IS NOT NULL AND NOT has_kyc_started"),
            "handling": "the assignment log proves KYC entry, so the experiment (ITT) still counts them",
        },
    }
    con.close()
    write_json("outputs/data_quality_report.json", {
        "simulated": True,
        "dedup_tolerance_seconds": tol,
        "duplicates": {"injected": inj["duplicate_events"], "detected_and_removed": int(detected_dups),
                       "match": int(detected_dups) == inj["duplicate_events"]},
        "legitimate_repeats_kept": {"total": int(repeats_kept), "by_event": {k: int(v) for k, v in
                                                                           repeats_by_event.items()},
                                    "ground_truth_kyc_retries": inj["legitimate_kyc_retries_present"]},
        "out_of_order": {"injected": inj["out_of_order_events"], "detected_and_corrected": int(ooo),
                         "by_event": {k: int(v) for k, v in ooo_by.items()},
                         "action": "timestamp set to the preceding stage's first timestamp; flagged ts_corrected",
                         "match": int(ooo) == inj["out_of_order_events"]},
        "null_device": {"injected": inj["null_device_users"], "labelled_unknown": int(null_dev)},
        "missing_preceding_stage": {"injected_users": inj["missing_step_users"],
                                    "users_excluded_from_later_stages": int(missing)},
        "unresolved_anomalies": unresolved,
        "handled_by_design": handled,
    })
    print(f"dups {detected_dups}/{inj['duplicate_events']}  ooo {ooo}/{inj['out_of_order_events']}  "
          f"repeats {repeats_kept}/{inj['legitimate_kyc_retries_present']}  missing-step {missing}")


if __name__ == "__main__":
    main()
