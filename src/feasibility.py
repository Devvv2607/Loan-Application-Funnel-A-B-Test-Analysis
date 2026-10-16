"""Phase 0.5: feasibility check, run BEFORE any data is generated.

Why this exists: a 50k-user budget is fixed in config. Before simulating, we ask
whether that budget can answer the questions we plan to ask:
  * the primary metric: can it detect the business-relevant MDE at alpha 0.05 and power 0.80?
  * each guardrail: is the expected one-sided 95% bound tight enough to rule out its
    non-inferiority margin? A guardrail that cannot be resolved will come back
    "inconclusive" whatever the truth, which makes "Ship" unreachable by design.

Two planning assumptions are reported for every guardrail:
  * "no_true_difference": the textbook non-inferiority power assumption (true diff = 0);
  * "planned_selection_effect": the difference implied by the planned simulation
    parameters (marginal applicants get through). This is the honest, more
    demanding case, because the treatment really does change who gets a loan.

The expected rates come from model.py, so they are exact expectations of the
generator, not guesses.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from scipy.stats import norm
from statsmodels.stats.power import NormalIndPower

from common import ROOT, load_brief, settings, sim_config, write_json
from model import expected_kyc_start_share, randomized_population_expectations


def mde_two_proportions(p1: float, n_per_arm: float, alpha: float, power: float) -> dict:
    """Smallest detectable absolute increase from baseline p1 (two-sided test)."""
    h = NormalIndPower().solve_power(nobs1=n_per_arm, alpha=alpha, power=power, ratio=1.0,
                                     alternative="two-sided")
    p2_h = math.sin(math.asin(math.sqrt(p1)) + h / 2) ** 2
    # Closed form with the pooled-variance approximation, as a cross-check.
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    d = z * math.sqrt(2 * p1 * (1 - p1) / n_per_arm)
    return {"mde_pp_cohens_h": (p2_h - p1) * 100, "mde_pp_closed_form": d * 100}


def ni_assessment(c: float, t: float, var_c_unit: float, var_t_unit: float, n_per_arm: float,
                  margin: float, direction: str, alpha: float, power: float, scale: float) -> dict:
    """Non-inferiority planning for one guardrail.

    var_*_unit is the variance contribution per randomized user (so the SE at
    n randomized users per arm is sqrt((var_c_unit + var_t_unit) / n)).
    direction "higher_is_worse": pass if upper bound < margin (margin > 0).
    direction "lower_is_worse": pass if lower bound > margin (margin < 0).
    """
    z_a, z_b = norm.ppf(1 - alpha), norm.ppf(power)
    se = math.sqrt((var_c_unit + var_t_unit) / n_per_arm)
    diff = t - c
    if direction == "higher_is_worse":
        bound, room = diff + z_a * se, margin - diff
    else:
        bound, room = diff - z_a * se, diff - margin
    prob_pass = float(norm.cdf(room / se - z_a))
    n_needed = (z_a + z_b) ** 2 * (var_c_unit + var_t_unit) / room ** 2 if room > 0 else None
    return {
        "control": c * scale, "treatment": t * scale, "expected_difference": diff * scale,
        "expected_se": se * scale, "expected_one_sided_bound": bound * scale,
        "expected_bound_inside_margin": bool(room > z_a * se),
        "probability_of_pass": prob_pass,
        "randomized_users_per_arm_for_80pct_pass_probability": math.ceil(n_needed) if n_needed else None,
    }


def planned_margins(plan: dict) -> tuple[dict, str]:
    """Margins from the frozen brief if it exists, else the initial planning values."""
    if (ROOT / "outputs" / "brief_freeze.json").exists():
        g = load_brief()["guardrails"]
        return {"delinquent_per_1000_randomized": g["delinquent_per_1000_randomized"]["margin"],
                "early_delinquency_rate_pp": g["early_delinquency_rate"]["margin_pp"],
                "approval_rate_pp": g["approval_rate"]["margin_pp"]}, "config/experiment_brief.yaml (frozen)"
    return plan["guardrail_margins"], "config/settings.yaml feasibility_plan (initial)"


def guardrails(e: dict, n: float, plan: dict, assume_no_diff: bool) -> dict:
    a, power = plan["guardrail_alpha_one_sided"], plan["power"]
    m, _ = planned_margins(plan)
    C, T = e["control"], e["treatment"]
    if assume_no_diff:
        T = C
    out = {}
    # (a) decision guardrail: delinquent loans per randomized user (Bernoulli per user).
    dc, dt = C["delinquent"], T["delinquent"]
    out["delinquent_per_1000_randomized"] = {
        "role": "decision", "unit": "per 1,000 randomized users", "margin": m["delinquent_per_1000_randomized"],
        **ni_assessment(dc, dt, dc * (1 - dc), dt * (1 - dt), n, m["delinquent_per_1000_randomized"] / 1000,
                        "higher_is_worse", a, power, 1000)}
    # (b) diagnostic: early delinquency rate among disbursed loans.
    rc, rt = C["delinquent"] / C["loans"], T["delinquent"] / T["loans"]
    out["early_delinquency_rate"] = {
        "role": "diagnostic", "unit": "pp", "margin": m["early_delinquency_rate_pp"],
        **ni_assessment(rc, rt, rc * (1 - rc) / C["loans"], rt * (1 - rt) / T["loans"], n,
                        m["early_delinquency_rate_pp"] / 100, "higher_is_worse", a, power, 100)}
    # (c) diagnostic: approval rate among credit decisions.
    ac, at = C["approvals"] / C["decisions"], T["approvals"] / T["decisions"]
    out["approval_rate"] = {
        "role": "diagnostic", "unit": "pp", "margin": m["approval_rate_pp"],
        **ni_assessment(ac, at, ac * (1 - ac) / C["decisions"], at * (1 - at) / T["decisions"], n,
                        m["approval_rate_pp"] / 100, "lower_is_worse", a, power, 100)}
    return out


def main() -> None:
    s, cfg = settings(), sim_config()
    plan, per = s["feasibility_plan"], s["periods"]
    total = cfg["population"]["total_users"]
    weeks = per["pre_period_weeks"] + per["experiment_weeks"]
    users_per_week = total / weeks
    kyc_share = expected_kyc_start_share(cfg)
    rand_per_week_per_arm = users_per_week * kyc_share / 2
    n = rand_per_week_per_arm * per["experiment_weeks"]
    e = randomized_population_expectations(cfg)

    p_kyc = e["control"]["kyc_completed"]
    primary = mde_two_proportions(p_kyc, n, plan["alpha"], plan["power"])
    primary.update({"baseline_kyc_completion_rate": p_kyc,
                    "business_mde_pp": plan["business_mde_pp"],
                    "detectable_at_business_mde": primary["mde_pp_cohens_h"] <= plan["business_mde_pp"]})
    p_dis = e["control"]["loans"]
    secondary = mde_two_proportions(p_dis, n, plan["alpha"], plan["power"])
    secondary["baseline_disbursal_share"] = p_dis

    g_null = guardrails(e, n, plan, assume_no_diff=True)
    g_sel = guardrails(e, n, plan, assume_no_diff=False)

    def weeks_needed(n_arm):
        return math.ceil(n_arm / rand_per_week_per_arm) if n_arm else None

    options = []
    for label, g in (("no_true_difference", g_null), ("planned_selection_effect", g_sel)):
        need = g["delinquent_per_1000_randomized"]["randomized_users_per_arm_for_80pct_pass_probability"]
        wk = weeks_needed(need)
        options.append({
            "assumption": label,
            "decision_guardrail_users_per_arm_needed": need,
            "experiment_weeks_needed_at_current_traffic": wk,
            "total_users_needed_at_current_traffic": math.ceil(users_per_week * (per["pre_period_weeks"] + wk))
            if wk else None,
        })

    issues = []
    if not primary["detectable_at_business_mde"]:
        issues.append("Primary metric cannot detect the business MDE with the planned sample.")
    for label, g in (("no_true_difference", g_null), ("planned_selection_effect", g_sel)):
        if not g["delinquent_per_1000_randomized"]["expected_bound_inside_margin"]:
            issues.append(f"Decision guardrail (delinquent loans per 1,000 randomized users) is not expected "
                          f"to resolve inside its margin under the '{label}' assumption.")

    write_json("outputs/feasibility.json", {
        "simulated": True,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plan": {
            "total_users": total, "pre_period_weeks": per["pre_period_weeks"],
            "experiment_weeks": per["experiment_weeks"], "users_per_week": users_per_week,
            "expected_kyc_start_share": kyc_share,
            "expected_randomized_users_per_arm": n,
            "expected_disbursed_loans_per_arm": {"control": n * e["control"]["loans"],
                                                 "treatment": n * e["treatment"]["loans"]},
            "alpha": plan["alpha"], "power": plan["power"],
            "margins_source": planned_margins(plan)[1],
        },
        "primary_kyc_completion": primary,
        "secondary_disbursal_share": secondary,
        "guardrails_assuming_no_true_difference": g_null,
        "guardrails_assuming_planned_selection_effect": g_sel,
        "options_to_resolve_decision_guardrail": options,
        "issues": issues,
        "feasible_as_planned": not issues,
    })


if __name__ == "__main__":
    main()
