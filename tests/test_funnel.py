"""Funnel tests: monotonic counts, pandas parity, drop-off shares, independent argmax."""

import numpy as np
import pandas as pd
import pytest

from common import ROOT, read_json
from ingest import connect

STAGES = ["application_started", "kyc_started", "kyc_completed", "decision_made", "loan_disbursed"]


@pytest.fixture(scope="module")
def flags():
    c = connect(read_only=True)
    df = c.execute("SELECT * FROM user_stage_flags WHERE period = 'pre'").df()
    c.close()
    return df


@pytest.fixture(scope="module")
def overall():
    return pd.read_csv(ROOT / "outputs" / "funnel_overall.csv")


def test_counts_non_increasing(overall):
    assert overall["users"].is_monotonic_decreasing


def test_sql_conversions_equal_pandas(flags, overall):
    counts = [int(flags[f"reached_{s}"].sum()) for s in STAGES]
    assert overall["users"].tolist() == counts
    conv = [counts[i] / counts[i - 1] for i in range(1, len(counts))]
    np.testing.assert_allclose(overall["conversion_from_prev"].iloc[1:], conv, rtol=0, atol=1e-9)


def test_segment_conversions_equal_pandas(flags):
    seg = pd.read_csv(ROOT / "outputs" / "funnel_segments.csv", dtype={"segment": str})
    for dim in ("device", "channel", "city_tier"):
        for level, g in flags.groupby(dim):
            counts = [int(g[f"reached_{s}"].sum()) for s in STAGES]
            rows = seg[(seg["dim"] == dim) & (seg["segment"] == str(level))].sort_values("stage_order")
            assert rows["users"].tolist() == counts, (dim, level)
            assert rows["users"].is_monotonic_decreasing


def test_dropoff_shares_sum_to_total(overall):
    steps = overall.dropna(subset=["dropped"])
    assert abs(steps["dropoff_share"].sum() - 1) < 1e-9
    assert steps["dropped"].sum() == overall["users"].iloc[0] - overall["users"].iloc[-1]
    assert read_json("outputs/funnel_summary.json")["total_dropped"] == steps["dropped"].sum()


def test_largest_dropoff_is_independent_argmax(flags):
    counts = np.array([flags[f"reached_{s}"].sum() for s in STAGES])
    lost = counts[:-1] - counts[1:]
    expected = STAGES[1 + int(np.argmax(lost))]
    assert read_json("outputs/funnel_summary.json")["largest_dropoff"]["stage"] == expected
