"""Method-validation tests (bands from the project brief) and segment-output sanity."""

import pandas as pd

from common import ROOT, read_json


def test_aa_false_positive_rate_in_band():
    assert 0.035 <= read_json("outputs/validation_sims.json")["aa_test"]["false_positive_rate"] <= 0.065


def test_ci_coverage_in_band():
    assert 0.92 <= read_json("outputs/validation_sims.json")["ci_coverage"]["coverage"] <= 0.98


def test_srm_flags_broken_and_passes_main():
    v = read_json("outputs/validation_sims.json")["srm_detection"]
    assert v["broken_dataset"]["p_value"] < 0.001
    assert not v["main_dataset"]["flagged"]


def test_peeking_inflates_false_positives():
    p = read_json("outputs/validation_sims.json")["peeking"]
    assert p["false_positive_rate_peeking"] > p["false_positive_rate_fixed_horizon"]


def test_segments_are_exploratory_and_holm_adjusted():
    seg = pd.read_csv(ROOT / "outputs" / "segment_effects.csv")
    assert (seg["label"] == "exploratory").all()
    assert (seg["p_holm"] >= seg["p_value"] - 1e-12).all()
    assert set(seg["dim"]) == {"device", "channel", "city_tier"}
