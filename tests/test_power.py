"""Power tests: method agreement, monotonicity, sample sufficiency, feasibility before simulation."""

import os
from datetime import datetime, timezone

from common import ROOT, read_json, settings
from power import n_closed_form, n_cohens_h


def test_methods_agree_within_2pct():
    pa = read_json("outputs/power_analysis.json")
    assert pa["required_users_per_arm"]["relative_difference"] < 0.02
    p1 = pa["inputs"]["baseline_kyc_completion_rate"]
    for mde in (0.01, 0.02, 0.03, 0.05):
        a, b = n_cohens_h(p1, p1 + mde, 0.05, 0.8), n_closed_form(p1, p1 + mde, 0.05, 0.8)
        assert abs(a - b) / b < 0.02


def test_required_n_increases_as_mde_decreases():
    p1 = read_json("outputs/power_analysis.json")["inputs"]["baseline_kyc_completion_rate"]
    ns = [n_cohens_h(p1, p1 + m, 0.05, 0.8) for m in (0.06, 0.05, 0.04, 0.03, 0.02, 0.01)]
    assert all(x < y for x, y in zip(ns, ns[1:]))


def test_experiment_has_required_n_per_arm():
    pa = read_json("outputs/power_analysis.json")
    assert pa["experiment_has_required_n"]
    assert min(pa["experiment_assignment_counts"].values()) >= pa["required_users_per_arm"]["used"]
    assert pa["duration"]["planned_covers_required"]


def test_feasibility_written_before_simulation_and_covers_all_guardrails():
    f = read_json("outputs/feasibility.json")
    written = datetime.strptime(f["generated_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    raw = ROOT / settings()["paths"]["raw_dir"] / "events.csv"
    simulated = datetime.fromtimestamp(os.path.getmtime(raw), tz=timezone.utc)
    assert written < simulated
    expected = {"delinquent_per_1000_randomized", "early_delinquency_rate", "approval_rate"}
    for key in ("guardrails_assuming_no_true_difference", "guardrails_assuming_planned_selection_effect"):
        assert set(f[key]) == expected
    assert set(read_json("outputs/power_analysis.json")["guardrail_precision"]) == expected


def test_brief_frozen_before_simulation():
    fz = read_json("outputs/brief_freeze.json")
    frozen = datetime.strptime(fz["frozen_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    raw = ROOT / settings()["paths"]["raw_dir"] / "events.csv"
    assert frozen < datetime.fromtimestamp(os.path.getmtime(raw), tz=timezone.utc)
