"""Phase 9: apply the pre-registered decision rule and generate the memo.

The rule is read from the frozen brief; this module only evaluates its
conditions on the results. Diagnostics are reported but cannot change the
decision, exactly as the brief states.
"""

from __future__ import annotations

from common import ROOT, load_brief, read_json, settings, write_json

LABELS = {"ship": "Ship", "iterate": "Iterate", "dont_ship": "Don't ship"}


def decide(primary_significant: bool, primary_diff: float, guardrail_label: str) -> str:
    """The brief's rule. Kept tiny so tests can re-derive it independently."""
    if not primary_significant or primary_diff <= 0:
        return "dont_ship"
    return "ship" if guardrail_label == "pass" else "iterate"


def fmt_ci(ci, nd=2):
    return f"[{ci[0]:.{nd}f}, {ci[1]:.{nd}f}]"


def memo(brief, res, grd, dec, funnel, val) -> str:
    p, s = res["primary"], res["secondary"]
    g = grd["guardrails"]
    ga, gb, gc = g["delinquent_per_1000_randomized"], g["early_delinquency_rate"], g["approval_rate"]
    n = res["assignment_counts"]
    lf = funnel["largest_dropoff"]
    extra = ga["extra_sample_to_resolve"]
    gt = res["ground_truth_comparison"]
    per = settings()["periods"]
    pre_w, exp_w = per["pre_period_weeks"], per["experiment_weeks"]
    lines = [
        "# Rollout recommendation: simplified KYC",
        "",
        "> **Simulated data.** Pebble Credit is fictional. Effects were planted in a data generator; this memo "
        "demonstrates the analysis method, not a real company's results.",
        "",
        f"**Decision under the pre-registered rule: {LABELS[dec['decision']]}**",
        "",
        "## Context",
        f"In the {pre_w}-week pre-period, the largest funnel drop-off was **{lf['transition']}**: "
        f"{lf['users_lost']:,} applicants lost ({lf['dropoff_share']:.1%} of all drop-off; "
        f"KYC completion rate {lf['conversion_from_prev']:.1%} of users who started KYC).",
        "",
        "## What we tested",
        f"A simplified KYC flow vs the current flow, randomized 50/50 at KYC start "
        f"({n['control']:,} control, {n['treatment']:,} treatment; sample-ratio check p = "
        f"{read_json('outputs/srm.json')['p_value']:.2f}). Analysis is intention-to-treat. The decision rule, "
        f"metrics and margins were frozen before any data existed.",
        "",
        "## Results",
        f"- **KYC completion rate (primary):** {p['control']['rate']:.1%} → {p['treatment']['rate']:.1%}, "
        f"**{p['diff_pp']:+.2f} pp** (95% CI {fmt_ci(p['diff_ci_pp'])} pp; relative lift "
        f"{p['relative_lift']:+.1%}, p = {p['p_value']:.1e}).",
        f"- **Disbursal share of randomized users (secondary):** {s['diff_pp']:+.2f} pp "
        f"(95% CI {fmt_ci(s['diff_ci_pp'])} pp). The KYC gain survives the credit decision.",
        f"- **Early-delinquent loans per 1,000 randomized users (decision guardrail):** "
        f"{ga['control']['value']:.2f} → {ga['treatment']['value']:.2f}, {ga['difference']:+.2f} "
        f"(one-sided 95% bound {ga['one_sided_95_bound']:+.2f} vs margin +{ga['margin']}): "
        f"**{ga['label']}**.",
        f"- Diagnostics: early delinquency rate per loan {gb['difference']:+.2f} pp (bound "
        f"{gb['one_sided_95_bound']:+.2f} vs +{gb['margin']}: {gb['label']}); approval rate "
        f"{gc['difference']:+.2f} pp (bound {gc['one_sided_95_bound']:+.2f} vs {gc['margin']}: {gc['label']}).",
        "",
        "Why the per-user count rises while the per-loan rate does not: the treatment arm disbursed "
        f"{grd['per_loan_vs_per_user']['loans_per_1000_randomized']['treatment']:.1f} loans per 1,000 randomized "
        f"users vs {grd['per_loan_vs_per_user']['loans_per_1000_randomized']['control']:.1f}, so it carries more "
        "delinquent loans even at an unchanged per-loan rate. Only the per-user count is a randomized comparison.",
        "",
        "## Decision",
    ]
    for c in dec["conditions"]:
        lines.append(f"- {'✓' if c['met'] else '✗'} {c['condition']}")
    if dec["decision"] == "iterate" and extra:
        need = extra["randomized_users_per_arm_for_bound_inside_margin_if_estimate_holds"]
        daily = read_json("outputs/power_analysis.json")["duration"]["daily_kyc_starts"]
        weeks = need / (daily / 2 * 7)
        lines += ["", f"The conversion gain is real, but the data cannot yet rule out an increase in early-delinquent "
                      f"loans beyond the break-even margin. Resolving it at the observed estimate would need about "
                      f"{need:,} randomized users per arm (vs {min(n.values()):,} now), roughly {weeks:,.0f} weeks "
                      f"of KYC traffic. The per-loan early delinquency rate shows no detectable deterioration "
                      f"({gb['difference']:+.2f} pp), so the open question is mostly precision: the guardrail's 95% "
                      f"CI spans {ga['ci95'][1] - ga['ci95'][0]:.1f} per 1,000, wider than the {ga['margin']} margin. "
                      f"A longer test is impractical at current traffic, so the guardrail is expected to be resolved "
                      f"by re-testing a tighter variant (one check kept for thin-file applicants) under a new "
                      f"pre-registered brief."]
    lines += [
        "",
        "## Risks",
        "- **Selection effect:** the simpler flow admits marginal applicants with weaker credit profiles.",
        "- **Outcome maturity:** early delinquency covers only the first EMI; later losses are not yet observable.",
        f"- **Novelty effect:** a {exp_w}-week test may overstate a lift that fades.",
        f"- **Simulated data:** results demonstrate the method. The true planted effect "
        f"({gt['primary_true_diff_pp']:+.2f} pp) {'lies inside' if gt['primary_true_inside_ci'] else 'lies outside'} "
        f"the 95% CI; A/A false-positive rate {val['aa_test']['false_positive_rate']:.1%}, CI coverage "
        f"{val['ci_coverage']['coverage']:.1%}.",
        "",
        "## Rollout plan",
    ]
    if dec["decision"] == "ship":
        lines.append("- Stage exposure 10% → 50% → 100%, two weeks per stage.")
    elif dec["decision"] == "iterate":
        lines += [
            "- Do not roll out to everyone. A staged 10% → 50% exposure limits credit risk while matured delinquency "
            "is monitored per cohort; it is a risk control, not a test, and is not expected to resolve the guardrail.",
            "- Resolve the guardrail by re-testing the tighter variant (one check kept for thin-file applicants) "
            "under a new pre-registered brief.",
        ]
    else:
        lines.append("- Do not roll out. Revisit the KYC design.")
    lines += [
        "- Monitor matured early-delinquent loans per 1,000 KYC entrants and the per-loan rate at 30 / 60 / 90 days "
        "after disbursal for each exposure cohort, against the rollback triggers below.",
        f"- **Rollback triggers:** the early-delinquent loans per 1,000 estimate exceeds the +{ga['margin']} margin "
        f"(guardrail fails) at any monitoring point, or the KYC completion gain's 95% CI falls below zero.",
        "",
        "*Analysis by Dev Mittal · every figure is computed by the pipeline and read from outputs/.*",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    brief = load_brief()
    res = read_json("outputs/experiment_results.json")
    grd = read_json("outputs/guardrails.json")
    funnel = read_json("outputs/funnel_summary.json")
    val = read_json("outputs/validation_sims.json")
    rule = brief["decision_rule"]
    gname = rule["decision_guardrail"]
    g = grd["guardrails"][gname]
    p = res["primary"]
    decision = decide(p["significant"], p["diff_pp"], g["label"])
    conditions = [
        {"condition": f"Primary metric significant (p = {p['p_value']:.1e} < {res['alpha']})",
         "met": bool(p["significant"])},
        {"condition": f"Primary effect positive ({p['diff_pp']:+.2f} pp)", "met": p["diff_pp"] > 0},
        {"condition": f"Decision guardrail passes non-inferiority (label: {g['label']})", "met": g["label"] == "pass"},
    ]
    dec = {
        "simulated": True,
        "decision": decision, "decision_label": LABELS[decision],
        "rule": rule, "conditions": conditions,
        "evidence": {"primary_diff_pp": p["diff_pp"], "primary_ci_pp": p["diff_ci_pp"], "primary_p": p["p_value"],
                     "decision_guardrail": gname, "guardrail_label": g["label"],
                     "guardrail_difference": g["difference"], "guardrail_bound": g["one_sided_95_bound"],
                     "guardrail_margin": g["margin"],
                     "diagnostics": {k: v["label"] for k, v in grd["guardrails"].items() if v["role"] == "diagnostic"}},
        "assignment_counts": res["assignment_counts"],
    }
    write_json("outputs/decision.json", dec)
    text = memo(brief, res, grd, dec, funnel, val)
    path = ROOT / settings()["paths"]["memo"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Decision: {LABELS[decision]}")


if __name__ == "__main__":
    main()
