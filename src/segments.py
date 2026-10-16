"""Phase 7: treatment effect by segment (EXPLORATORY).

Segments were not pre-registered as decision criteria, and testing many of them
inflates false positives, so p-values are Holm-adjusted across all segment tests
and nothing here feeds the shipping decision. Each estimate is compared with its
true planted effect to show how noisy subgroup estimates are, even when the
overall effect is recovered well.

Segment membership (device, channel, tier) is fixed before randomization, so
within-segment comparisons remain randomized.
"""

from __future__ import annotations

import pandas as pd
from statsmodels.stats.multitest import multipletests

from abstats import newcombe_diff_ci, ztest_two_proportions
from common import ROOT, load_brief, read_json, write_json
from ingest import connect


def main() -> None:
    alpha = load_brief()["primary_metric"]["alpha"]
    con = connect(read_only=True)
    rows = []
    for dim in ("device", "channel", "city_tier"):
        df = con.execute(f"""SELECT {dim} AS segment, variant, COUNT(*) AS n, SUM(kyc_completed::INT) AS x
                             FROM experiment_users GROUP BY ALL ORDER BY ALL""").df()
        for seg, g in df.groupby("segment", sort=True):
            g = g.set_index("variant")
            nc, xc, nt, xt = (int(g.at["control", "n"]), int(g.at["control", "x"]),
                              int(g.at["treatment", "n"]), int(g.at["treatment", "x"]))
            z, p = ztest_two_proportions(xc, nc, xt, nt)
            lo, hi = newcombe_diff_ci(xc, nc, xt, nt, alpha)
            rows.append({"dim": dim, "segment": str(seg), "control_n": nc, "treatment_n": nt,
                         "control_rate": xc / nc, "treatment_rate": xt / nt, "diff_pp": (xt / nt - xc / nc) * 100,
                         "ci_low_pp": lo * 100, "ci_high_pp": hi * 100, "p_value": p})
    con.close()
    out = pd.DataFrame(rows)
    reject, p_holm, _, _ = multipletests(out["p_value"], alpha=alpha, method="holm")
    out["p_holm"] = p_holm
    out["significant_after_holm"] = reject
    truth = read_json("outputs/ground_truth.json")["treatment_effect_by_segment"]
    out["true_diff_pp"] = [truth.get(f"{d}={s}", {}).get("kyc_completion_diff_pp") for d, s in
                           zip(out["dim"], out["segment"])]
    out["true_inside_ci"] = [None if pd.isna(t) else bool(lo <= t <= hi) for t, lo, hi in
                             zip(out["true_diff_pp"], out["ci_low_pp"], out["ci_high_pp"])]
    out["label"] = "exploratory"
    known = out[out["true_diff_pp"].notna()]
    write_json("outputs/segment_summary.json", {
        "simulated": True, "label": "exploratory", "correction": "Holm across all segment tests",
        "segments_tested": int(len(out)),
        "significant_after_holm": int(out["significant_after_holm"].sum()),
        "segments_with_known_truth": int(len(known)),
        "true_effect_inside_ci": int(known["true_inside_ci"].sum()),
        "largest_estimate": {"segment": f"{out.loc[out['diff_pp'].idxmax(), 'dim']}="
                                        f"{out.loc[out['diff_pp'].idxmax(), 'segment']}",
                             "diff_pp": float(out["diff_pp"].max())},
    })
    out.to_csv(ROOT / "outputs" / "segment_effects.csv", index=False, lineterminator="\n", float_format="%.10g")
    print(out[["dim", "segment", "control_n", "diff_pp", "ci_low_pp", "ci_high_pp", "p_holm", "true_diff_pp",
               "true_inside_ci"]].to_string(index=False))


if __name__ == "__main__":
    main()
