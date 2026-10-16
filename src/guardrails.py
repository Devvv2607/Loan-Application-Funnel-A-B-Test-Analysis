"""Phase 6: guardrails as one-sided non-inferiority tests.

Why non-inferiority: "no significant increase in delinquency" is not evidence
that delinquency did not rise; a small, noisy experiment fails to detect harm
by default. Instead we ask whether the data RULE OUT a harmful increase: the
one-sided 95% confidence bound (the matching limit of a two-sided 90% Newcombe
interval) must lie inside the pre-registered margin.

Labels (from the brief's pass rule):
  pass         - bound inside the margin
  fail         - point estimate beyond the margin
  inconclusive - point estimate inside, bound crossing the margin
"""

from __future__ import annotations

import math

from scipy.stats import norm

from abstats import newcombe_diff_ci
from clean import run_sql
from common import load_brief, write_json
from ingest import connect

SCALE = {"delinquent_per_1000_randomized": 1000, "early_delinquency_rate": 100, "approval_rate": 100}
UNIT = {"delinquent_per_1000_randomized": "per 1,000 randomized users", "early_delinquency_rate": "pp",
        "approval_rate": "pp"}


def classify(point: float, bound: float, margin: float, direction: str) -> str:
    """Apply the pre-registered pass rule. Inputs share one scale."""
    if direction == "higher_is_worse":
        if point > margin:
            return "fail"
        return "pass" if bound < margin else "inconclusive"
    if point < margin:
        return "fail"
    return "pass" if bound > margin else "inconclusive"


def margin_of(spec: dict) -> float:
    return spec["margin"] if "margin" in spec else spec["margin_pp"]


def main() -> None:
    brief = load_brief()
    con = connect()
    run_sql(con, "07_guardrails.sql")
    rows = con.execute("SELECT * FROM guardrail_inputs").df()
    arms = dict(con.execute("SELECT variant, COUNT(*) FROM experiment_users GROUP BY 1 ORDER BY 1").fetchall())
    con.close()
    z1 = norm.ppf(0.95)

    out = {}
    for name, spec in brief["guardrails"].items():
        r = rows[rows["guardrail"] == name].set_index("variant")
        xc, nc = int(r.at["control", "numerator"]), int(r.at["control", "denominator"])
        xt, nt = int(r.at["treatment", "numerator"]), int(r.at["treatment", "denominator"])
        k, direction, margin = SCALE[name], spec["direction"], margin_of(spec)
        pc, pt = xc / nc, xt / nt
        diff = (pt - pc) * k
        lo95, hi95 = (v * k for v in newcombe_diff_ci(xc, nc, xt, nt, 0.05))
        lo90, hi90 = (v * k for v in newcombe_diff_ci(xc, nc, xt, nt, 0.10))
        bound = hi90 if direction == "higher_is_worse" else lo90
        label = classify(diff, bound, margin, direction)

        # Extra randomized users per arm to resolve an inconclusive result, if the
        # observed point estimate and variances held. Diagnostic denominators are
        # converted to randomized users via the observed loans/decisions per user.
        room = (margin - diff) if direction == "higher_is_worse" else (diff - margin)
        var_unit = (pc * (1 - pc) / (nc / arms["control"]) + pt * (1 - pt) / (nt / arms["treatment"])) * k * k
        need = None
        if label == "inconclusive" and room > 0:
            cur = min(arms.values())
            n50 = math.ceil(z1 ** 2 * var_unit / room ** 2)
            n80 = math.ceil((z1 + norm.ppf(0.8)) ** 2 * var_unit / room ** 2)
            need = {"randomized_users_per_arm_for_bound_inside_margin_if_estimate_holds": n50,
                    "additional_users_per_arm": max(0, n50 - cur),
                    "randomized_users_per_arm_for_80pct_chance": n80,
                    "additional_users_per_arm_for_80pct_chance": max(0, n80 - cur)}
        out[name] = {
            "role": spec["role"], "name": spec["name"], "unit": UNIT[name], "direction": direction,
            "control": {"numerator": xc, "denominator": nc, "value": pc * k},
            "treatment": {"numerator": xt, "denominator": nt, "value": pt * k},
            "difference": diff, "ci95": [lo95, hi95], "one_sided_95_bound": bound, "margin": margin,
            "label": label, "margin_rationale": " ".join(spec["margin_rationale"].split()),
            "extra_sample_to_resolve": need,
        }

    a, b = out["delinquent_per_1000_randomized"], out["early_delinquency_rate"]
    loans_c, loans_t = b["control"]["denominator"], b["treatment"]["denominator"]
    lpu_c, lpu_t = loans_c / arms["control"] * 1000, loans_t / arms["treatment"] * 1000
    explanation = (
        f"Per loan, the early delinquency rate moved from {b['control']['value']:.2f}% to "
        f"{b['treatment']['value']:.2f}% ({b['difference']:+.2f}pp). Per 1,000 randomized users, early-delinquent "
        f"loans moved from {a['control']['value']:.2f} to {a['treatment']['value']:.2f} ({a['difference']:+.2f}). "
        f"The per-user count rises mechanically with conversion: the treatment arm disbursed {lpu_t:.1f} loans "
        f"per 1,000 randomized users vs {lpu_c:.1f} in control, so it carries more delinquent loans even at an "
        f"unchanged per-loan rate. The per-loan rate compares different borrower mixes, because the simpler flow "
        f"lets marginal applicants through, so only the per-user count is a randomized comparison, and only it "
        f"decides."
    )
    write_json("outputs/guardrails.json", {
        "simulated": True,
        "assignment_counts": {k: int(v) for k, v in arms.items()},
        "pass_rule": brief["guardrail_pass_rule"],
        "decision_guardrail": brief["decision_rule"]["decision_guardrail"],
        "guardrails": out,
        "per_loan_vs_per_user": {"loans_per_1000_randomized": {"control": lpu_c, "treatment": lpu_t},
                                 "explanation": explanation},
        "outcome_maturity_note": "Early delinquency covers only the first EMI (30+ days past due). Later "
                                 "delinquency and eventual losses are not yet observable for these loans.",
    })
    for n, g in out.items():
        print(f"{n:32s} diff={g['difference']:+.3f} ci95={[round(v, 3) for v in g['ci95']]} "
              f"bound={g['one_sided_95_bound']:+.3f} margin={g['margin']} -> {g['label']}")
    print(explanation)
    print("extra sample (decision):", out["delinquent_per_1000_randomized"]["extra_sample_to_resolve"])


if __name__ == "__main__":
    main()
