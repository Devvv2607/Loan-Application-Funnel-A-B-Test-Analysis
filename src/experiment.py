"""Phase 5: experiment analysis (SRM check, primary, secondary, ground truth).

Order matters:
  1. The brief is loaded first; without a frozen decision rule nothing runs.
  2. SRM check before any outcome is looked at. If assignment counts deviate
     from 50/50 beyond chance (p < 0.001), the randomization or logging is broken
     and every downstream comparison is suspect, so we stop rather than report a
     possibly biased effect.
  3. Primary metric, intention-to-treat: denominator = everyone randomized in the
     arm at KYC start. Conditioning on post-randomization behaviour (e.g. only
     users who finished KYC) would compare different kinds of users and break
     the randomization that makes the comparison causal.
"""

from __future__ import annotations

import pandas as pd
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest

from abstats import newcombe_diff_ci, ratio_ci_log, srm_chisquare, wilson, ztest_two_proportions
from clean import run_sql
from common import ROOT, load_brief, read_json, write_json
from ingest import connect


class SRMError(RuntimeError):
    pass


def compare(xc: int, nc: int, xt: int, nt: int, alpha: float) -> dict:
    """Treatment minus control: rates, z-test, Newcombe CI, relative lift, statsmodels cross-checks."""
    z, p = ztest_two_proportions(xc, nc, xt, nt)
    lo, hi = newcombe_diff_ci(xc, nc, xt, nt, alpha)
    r, rlo, rhi = ratio_ci_log(xc, nc, xt, nt, alpha)
    sm_z, sm_p = proportions_ztest([xt, xc], [nt, nc])
    sm_lo, sm_hi = confint_proportions_2indep(xt, nt, xc, nc, method="newcomb", compare="diff", alpha=alpha)
    sm_rlo, sm_rhi = confint_proportions_2indep(xt, nt, xc, nc, method="log", compare="ratio", alpha=alpha)
    return {
        "control": {"numerator": xc, "denominator": nc, "rate": xc / nc, "wilson_ci": list(wilson(xc, nc, alpha))},
        "treatment": {"numerator": xt, "denominator": nt, "rate": xt / nt, "wilson_ci": list(wilson(xt, nt, alpha))},
        "diff_pp": (xt / nt - xc / nc) * 100,
        "diff_ci_pp": [lo * 100, hi * 100],
        "relative_lift": r - 1,
        "relative_lift_ci": [rlo - 1, rhi - 1],
        "z": z, "p_value": p,
        "significant": p < alpha,
        "cross_check_statsmodels": {"z": float(sm_z), "p_value": float(sm_p), "diff_ci_pp": [sm_lo * 100, sm_hi * 100],
                                    "relative_lift_ci": [sm_rlo - 1, sm_rhi - 1]},
    }


def main() -> None:
    brief = load_brief()
    alpha = brief["primary_metric"]["alpha"]
    con = connect()
    run_sql(con, "06_experiment_metrics.sql")
    arms = con.execute("SELECT * FROM experiment_arm_metrics").df().set_index("variant")
    daily = con.execute("SELECT * FROM experiment_daily ORDER BY assigned_date, variant").df()
    con.close()

    nc, nt = int(arms.at["control", "randomized"]), int(arms.at["treatment", "randomized"])
    stat, p_srm = srm_chisquare([nc, nt], [0.5, 0.5])
    srm = {"simulated": True, "expected_share": [0.5, 0.5],
           "observed": {"control": nc, "treatment": nt}, "expected": {"control": (nc + nt) / 2,
                                                                       "treatment": (nc + nt) / 2},
           "treatment_share": nt / (nc + nt), "chi2": stat, "p_value": p_srm, "threshold": 0.001,
           "passed": p_srm >= 0.001}
    write_json("outputs/srm.json", srm)
    if not srm["passed"]:
        raise SRMError(f"Sample ratio mismatch (p={p_srm:.2e}); analysis stopped.")

    c, t = arms.loc["control"], arms.loc["treatment"]
    primary = compare(int(c["kyc_completed"]), nc, int(t["kyc_completed"]), nt, alpha)
    secondary = compare(int(c["disbursed"]), nc, int(t["disbursed"]), nt, alpha)

    gt = read_json("outputs/ground_truth.json")["treatment_effect"]
    truth = {
        "primary_true_diff_pp": gt["kyc_completion_diff_pp"],
        "primary_true_inside_ci": primary["diff_ci_pp"][0] <= gt["kyc_completion_diff_pp"] <= primary["diff_ci_pp"][1],
        "primary_estimate_minus_truth_pp": primary["diff_pp"] - gt["kyc_completion_diff_pp"],
        "primary_true_relative_lift": gt["kyc_completion_relative_lift"],
        "secondary_true_diff_pp": gt["disbursal_share_diff_pp"],
        "secondary_true_inside_ci": secondary["diff_ci_pp"][0] <= gt["disbursal_share_diff_pp"]
        <= secondary["diff_ci_pp"][1],
    }
    write_json("outputs/experiment_results.json", {
        "simulated": True,
        "analysis": "intention-to-treat; denominator = all users randomized at KYC start in the arm",
        "assignment_counts": {"control": nc, "treatment": nt},
        "arm_counts": {arm: {k: int(v) for k, v in arms.loc[arm].items()} for arm in ("control", "treatment")},
        "alpha": alpha,
        "primary": {"metric": brief["primary_metric"]["name"], **primary},
        "secondary": {"metric": brief["secondary_metrics"][0]["name"], **secondary},
        "ground_truth_comparison": truth,
    })

    # Cumulative effect by day: what a "peeker" would have seen each day.
    w = daily.pivot(index="assigned_date", columns="variant", values=["cum_randomized", "cum_kyc_completed"]).ffill()
    rows = []
    for i, (d, r) in enumerate(w.iterrows(), start=1):
        xc_, nc_ = int(r[("cum_kyc_completed", "control")]), int(r[("cum_randomized", "control")])
        xt_, nt_ = int(r[("cum_kyc_completed", "treatment")]), int(r[("cum_randomized", "treatment")])
        z_, p_ = ztest_two_proportions(xc_, nc_, xt_, nt_)
        lo_, hi_ = newcombe_diff_ci(xc_, nc_, xt_, nt_, alpha)
        rows.append({"day": i, "date": pd.Timestamp(d).strftime("%Y-%m-%d"), "control_n": nc_, "treatment_n": nt_,
                     "control_rate": xc_ / nc_, "treatment_rate": xt_ / nt_, "diff_pp": (xt_ / nt_ - xc_ / nc_) * 100,
                     "ci_low_pp": lo_ * 100, "ci_high_pp": hi_ * 100, "p_value": p_})
    pd.DataFrame(rows).to_csv(ROOT / "outputs" / "daily_cumulative.csv", index=False, lineterminator="\n",
                              float_format="%.10g")
    print(f"SRM p={p_srm:.3f}  primary diff={primary['diff_pp']:.2f}pp CI={primary['diff_ci_pp']} "
          f"p={primary['p_value']:.2e}  truth={gt['kyc_completion_diff_pp']:.2f} inside={truth['primary_true_inside_ci']}")
    print(f"secondary diff={secondary['diff_pp']:.2f}pp CI={secondary['diff_ci_pp']} p={secondary['p_value']:.3g}")


if __name__ == "__main__":
    main()
