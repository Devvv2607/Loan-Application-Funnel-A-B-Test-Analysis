"""Guardrail tests: pass rule, decision guardrail choice, independent recomputation."""

import pandas as pd

from common import ROOT, load_brief, read_json
from guardrails import classify


def test_non_inferiority_labels_higher_is_worse():
    assert classify(point=0.5, bound=1.8, margin=2.1, direction="higher_is_worse") == "pass"
    assert classify(point=2.5, bound=4.0, margin=2.1, direction="higher_is_worse") == "fail"
    assert classify(point=1.0, bound=3.0, margin=2.1, direction="higher_is_worse") == "inconclusive"


def test_non_inferiority_labels_lower_is_worse():
    assert classify(point=-0.5, bound=-2.0, margin=-3.0, direction="lower_is_worse") == "pass"
    assert classify(point=-3.5, bound=-5.0, margin=-3.0, direction="lower_is_worse") == "fail"
    assert classify(point=-1.0, bound=-3.4, margin=-3.0, direction="lower_is_worse") == "inconclusive"


def test_reported_labels_follow_rule():
    for g in read_json("outputs/guardrails.json")["guardrails"].values():
        assert g["label"] == classify(g["difference"], g["one_sided_95_bound"], g["margin"], g["direction"])
        lo, hi = g["ci95"]
        assert lo <= g["difference"] <= hi


def test_decision_guardrail_is_per_randomized_user():
    brief = load_brief()
    assert brief["decision_rule"]["decision_guardrail"] == "delinquent_per_1000_randomized"
    assert brief["guardrails"]["delinquent_per_1000_randomized"]["role"] == "decision"
    assert brief["guardrails"]["early_delinquency_rate"]["role"] == "diagnostic"


def test_delinquent_per_1000_recomputed_from_raw_files():
    raw = ROOT / "data" / "raw"
    users = pd.read_csv(raw / "users.csv")
    ev = pd.read_csv(raw / "events.csv")
    loans = pd.read_csv(raw / "loans.csv")
    has = {e: set(ev.loc[ev["event_name"] == e, "user_id"]) for e in ev["event_name"].unique()}
    approved = set(ev.loc[ev["decision_outcome"] == "approved", "user_id"])
    bad = set(loans.loc[loans["dpd_30_on_first_emi"] == 1, "user_id"])
    chain = has["kyc_completed"] & has["decision_made"] & approved & has["loan_disbursed"] & bad
    g = read_json("outputs/guardrails.json")["guardrails"]["delinquent_per_1000_randomized"]
    for arm in ("control", "treatment"):
        ids = set(users.loc[users["variant"] == arm, "user_id"])
        assert g[arm]["numerator"] == len(ids & chain)
        assert abs(g[arm]["value"] - len(ids & chain) / len(ids) * 1000) < 1e-9
