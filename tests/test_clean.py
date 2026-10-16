"""Cleaning tests: injected vs detected issues, retries preserved, funnel monotonic, pandas parity."""

import duckdb
import pandas as pd
import pytest

from clean import run_sql
from common import ROOT, read_json, settings
from ingest import connect

TOL = settings()["cleaning"]["dedup_tolerance_seconds"]
STAGES = ["reached_application_started", "reached_kyc_started", "reached_kyc_completed",
          "reached_decision_made", "reached_loan_disbursed"]


@pytest.fixture(scope="module")
def con():
    c = connect(read_only=True)
    yield c
    c.close()


def test_detected_issues_match_injected():
    dq, inj = read_json("outputs/data_quality_report.json"), read_json("outputs/injected_issues.json")
    assert dq["duplicates"]["detected_and_removed"] == inj["duplicate_events"]
    assert dq["out_of_order"]["detected_and_corrected"] == inj["out_of_order_events"]
    assert dq["out_of_order"]["by_event"] == inj["out_of_order_by_stage"]
    assert dq["null_device"]["labelled_unknown"] == inj["null_device_users"]
    assert dq["missing_preceding_stage"]["users_excluded_from_later_stages"] == inj["missing_step_users"]
    assert all(v == 0 for v in dq["unresolved_anomalies"].values())


def test_legitimate_retries_preserved():
    dq, gt = read_json("outputs/data_quality_report.json"), read_json("outputs/ground_truth.json")
    assert dq["legitimate_repeats_kept"]["total"] == gt["realised"]["legitimate_kyc_retries"]


def _clean_synthetic(gap_seconds: int) -> int:
    c = duckdb.connect()
    c.execute("CREATE TABLE raw_users (user_id VARCHAR, signup_ts TIMESTAMP, device VARCHAR, channel VARCHAR, "
              "city_tier VARCHAR, period VARCHAR, variant VARCHAR, assigned_ts TIMESTAMP)")
    c.execute("CREATE TABLE raw_events AS SELECT * FROM (VALUES "
              "('E1','U1','application_started', TIMESTAMP '2026-03-02 10:00:00', NULL::VARCHAR), "
              f"('E2','U1','kyc_started', TIMESTAMP '2026-03-02 10:10:00', NULL), "
              f"('E3','U1','kyc_started', TIMESTAMP '2026-03-02 10:10:00' + INTERVAL {gap_seconds} SECOND, NULL)"
              ") t(event_id, user_id, event_name, event_ts, decision_outcome)")
    run_sql(c, "01_clean_events.sql", dedup_tolerance_seconds=TOL)
    n = c.execute("SELECT COUNT(*) FROM events_clean WHERE event_name = 'kyc_started'").fetchone()[0]
    c.close()
    return n


def test_retry_two_hours_apart_kept_two_seconds_apart_deduped():
    assert _clean_synthetic(2 * 3600) == 2
    assert _clean_synthetic(2) == 1


def test_stage_counts_non_increasing_overall_and_by_segment(con):
    df = con.execute("SELECT * FROM user_stage_flags").df()
    for keys in ([], ["period"], ["device"], ["channel"], ["city_tier"], ["signup_week"]):
        groups = [("all", df)] if not keys else df.groupby(keys)
        for name, g in groups:
            counts = [int(g[s].sum()) for s in STAGES]
            assert counts == sorted(counts, reverse=True), (keys, name, counts)


def test_sql_funnel_matches_independent_pandas(con):
    """Recompute cleaning + strict funnel from the raw CSV in pandas, compare to SQL."""
    raw = ROOT / settings()["paths"]["raw_dir"]
    ev = pd.read_csv(raw / "events.csv", parse_dates=["event_ts"])
    ev["outcome_key"] = ev["decision_outcome"].fillna("")
    ev = ev.sort_values(["user_id", "event_name", "outcome_key", "event_ts", "event_id"])
    gap = ev.groupby(["user_id", "event_name", "outcome_key"])["event_ts"].diff().dt.total_seconds()
    ev = ev[~(gap <= TOL)]
    has = {e: set(ev.loc[ev["event_name"] == e, "user_id"]) for e in ev["event_name"].unique()}
    approved = set(ev.loc[ev["decision_outcome"] == "approved", "user_id"])
    reach = has["application_started"]
    expected = [len(reach)]
    for e in ["kyc_started", "kyc_completed", "decision_made"]:
        reach = reach & has[e]
        expected.append(len(reach))
    expected.append(len(reach & approved & has["loan_disbursed"]))
    sql = con.execute("SELECT " + ", ".join(f"SUM({s}::INT)" for s in STAGES) + " FROM user_stage_flags").fetchone()
    assert list(sql) == expected
