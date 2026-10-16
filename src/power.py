"""Phase 4: power analysis from the observed pre-period baseline.

The MDE, alpha and power come from the frozen brief; only the baseline rates
come from data, and only from the PRE-period (no experiment outcomes are read).
The single experiment-period quantity used is the count of randomized users per
arm, which is traffic, not an outcome: we need it to confirm the planned
duration delivers the required sample.

Two independent sample-size methods are computed and must agree within 2%:
  * statsmodels NormalIndPower on Cohen's h (arcsine-transformed difference);
  * the closed-form two-proportion formula
    n = (z_{1-a/2} sqrt(2 pbar qbar) + z_{1-b} sqrt(p1 q1 + p2 q2))^2 / (p2 - p1)^2.
"""

from __future__ import annotations

import math

import pandas as pd
from scipy.stats import norm
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from common import ROOT, load_brief, settings, write_json
from ingest import connect


def n_cohens_h(p1: float, p2: float, alpha: float, power: float) -> float:
    h = abs(proportion_effectsize(p2, p1))
    return NormalIndPower().solve_power(effect_size=h, alpha=alpha, power=power, ratio=1.0,
                                        alternative="two-sided")


def n_closed_form(p1: float, p2: float, alpha: float, power: float) -> float:
    za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power)
    pbar = (p1 + p2) / 2
    num = za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return num ** 2 / (p2 - p1) ** 2


def mde_for_n(p1: float, n: float, alpha: float, power: float) -> float:
    """MDE (absolute) detectable with n per arm, via Cohen's h inverted."""
    h = NormalIndPower().solve_power(nobs1=n, alpha=alpha, power=power, ratio=1.0, alternative="two-sided")
    return math.sin(math.asin(math.sqrt(p1)) + h / 2) ** 2 - p1


def main() -> None:
    brief, s = load_brief(), settings()
    pm = brief["primary_metric"]
    alpha, power, mde = pm["alpha"], pm["power"], pm["mde_pp"] / 100
    g_alpha = 0.05
    pre_days = 7 * s["periods"]["pre_period_weeks"]

    con = connect(read_only=True)
    pre = con.execute("""
        SELECT SUM(reached_kyc_started::INT) AS kyc_starters,
               SUM(reached_kyc_completed::INT) AS kyc_completers,
               SUM(reached_loan_disbursed::INT) AS loans,
               SUM((reached_loan_disbursed AND dpd_30_on_first_emi = 1)::INT) AS delinquent,
               SUM(reached_decision_made::INT) AS decisions,
               SUM((reached_decision_made AND has_approval)::INT) AS approvals
        FROM user_stage_flags WHERE period = 'pre'""").df().iloc[0]
    arms = dict(con.execute("SELECT variant, COUNT(*) FROM users_clean WHERE variant IS NOT NULL "
                            "GROUP BY 1 ORDER BY 1").fetchall())
    con.close()

    p1 = pre["kyc_completers"] / pre["kyc_starters"]
    p2 = p1 + mde
    n_h, n_cf = n_cohens_h(p1, p2, alpha, power), n_closed_form(p1, p2, alpha, power)
    n_req = math.ceil(n_h)
    daily_kyc_starts = pre["kyc_starters"] / pre_days
    weeks_req = math.ceil(n_req / (daily_kyc_starts / 2 * 7))
    min_arm = min(arms.values())

    curve = pd.DataFrame({"users_per_arm": list(range(1000, 30001, 500))})
    curve["mde_pp"] = [mde_for_n(p1, n, alpha, power) * 100 for n in curve["users_per_arm"]]
    curve["weeks_of_traffic"] = curve["users_per_arm"] / (daily_kyc_starts / 2 * 7)
    curve.to_csv(ROOT / "outputs" / "mde_curve.csv", index=False, lineterminator="\n", float_format="%.10g")

    # Guardrail precision at the planned sample, from pre-period baselines, assuming no true difference.
    za, zb = norm.ppf(1 - g_alpha), norm.ppf(power)
    n_plan = n_req
    g = brief["guardrails"]
    d_user = pre["delinquent"] / pre["kyc_starters"]
    loans_per_user = pre["loans"] / pre["kyc_starters"]
    dec_per_user = pre["decisions"] / pre["kyc_starters"]
    r_loan = pre["delinquent"] / pre["loans"]
    a_rate = pre["approvals"] / pre["decisions"]
    specs = {
        "delinquent_per_1000_randomized": (2 * d_user * (1 - d_user), g["delinquent_per_1000_randomized"]["margin"]
                                           / 1000, 1000),
        "early_delinquency_rate": (2 * r_loan * (1 - r_loan) / loans_per_user,
                                   g["early_delinquency_rate"]["margin_pp"] / 100, 100),
        "approval_rate": (2 * a_rate * (1 - a_rate) / dec_per_user, abs(g["approval_rate"]["margin_pp"]) / 100, 100),
    }
    precision = {}
    for name, (var_unit, margin, scale) in specs.items():
        out = {}
        for label, n_ in (("at_required_primary_n", n_plan), ("at_actual_randomized_n", min_arm)):
            se = math.sqrt(var_unit / n_)
            sign = -1 if name == "approval_rate" else 1  # lower is worse: the bound sits below zero
            out[label] = {"users_per_arm": int(n_), "expected_se": se * scale,
                          "expected_bound_if_no_true_difference": sign * za * se * scale,
                          "margin": sign * margin * scale,
                          "bound_inside_margin": bool(za * se < margin)}
        out["users_per_arm_for_80pct_power_if_no_true_difference"] = math.ceil((za + zb) ** 2 * var_unit / margin ** 2)
        out["role"] = g[name]["role"]
        precision[name] = out

    write_json("outputs/power_analysis.json", {
        "simulated": True,
        "inputs": {"baseline_source": "pre-period KYC completion rate (users who started KYC)",
                   "baseline_kyc_completion_rate": p1, "mde_pp": mde * 100, "alpha": alpha, "power": power,
                   "pre_period_kyc_starters": int(pre["kyc_starters"]),
                   "pre_period_kyc_completers": int(pre["kyc_completers"])},
        "required_users_per_arm": {"statsmodels_cohens_h": n_h, "closed_form": n_cf,
                                   "relative_difference": abs(n_h - n_cf) / n_cf, "used": n_req},
        "duration": {"daily_kyc_starts": daily_kyc_starts, "weeks_required": weeks_req,
                     "weeks_planned": brief["experiment_weeks"],
                     "planned_covers_required": weeks_req <= brief["experiment_weeks"]},
        "experiment_assignment_counts": {k: int(v) for k, v in arms.items()},
        "experiment_has_required_n": bool(min_arm >= n_req),
        "guardrail_precision": precision,
    })
    print(f"baseline={p1:.4f} n_h={n_h:.0f} n_cf={n_cf:.0f} weeks={weeks_req} arms={arms} ok={min_arm >= n_req}")
    if min_arm < n_req:
        raise SystemExit("STOP: experiment period has fewer randomized users per arm than required.")


if __name__ == "__main__":
    main()
