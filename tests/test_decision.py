"""Decision tests: independent re-derivation, memo consistency, terminology."""

from common import ROOT, load_brief, read_json


def test_decision_rederived_independently():
    brief = load_brief()
    res, grd = read_json("outputs/experiment_results.json"), read_json("outputs/guardrails.json")
    p = res["primary"]
    sig = p["p_value"] < brief["primary_metric"]["alpha"]
    label = grd["guardrails"][brief["decision_rule"]["decision_guardrail"]]["label"]
    if sig and p["diff_pp"] > 0 and label == "pass":
        expected = "ship"
    elif sig and p["diff_pp"] > 0:
        expected = "iterate"
    else:
        expected = "dont_ship"
    assert read_json("outputs/decision.json")["decision"] == expected


def test_decision_uses_per_user_guardrail_not_per_loan():
    d = read_json("outputs/decision.json")
    assert d["evidence"]["decision_guardrail"] == "delinquent_per_1000_randomized"
    g = read_json("outputs/guardrails.json")["guardrails"]["delinquent_per_1000_randomized"]
    assert d["evidence"]["guardrail_label"] == g["label"]


def test_memo_uses_same_assignment_counts_and_decision():
    memo = (ROOT / "memo" / "recommendation.md").read_text(encoding="utf-8")
    counts = read_json("outputs/experiment_results.json")["assignment_counts"]
    assert f"{counts['control']:,} control" in memo and f"{counts['treatment']:,} treatment" in memo
    assert read_json("outputs/decision.json")["decision_label"] in memo
    assert "Simulated data" in memo
