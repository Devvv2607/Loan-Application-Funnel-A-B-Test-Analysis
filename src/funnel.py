"""Phase 3: pre-period funnel analysis (SQL), written to outputs/.

The largest drop-off is identified from the data, never assumed: it is the
transition that loses the most users (the largest share of total drop-off).
The lowest stage-to-stage conversion rate is reported alongside as a second
lens, and the summary records whether the two agree and how consistently the
same transition ranks worst across segments.
"""

from __future__ import annotations

import pandas as pd
from statsmodels.stats.proportion import proportion_confint

from clean import run_sql
from common import ROOT, write_json
from ingest import connect

LABELS = {
    "kyc_started": "Application → KYC start",
    "kyc_completed": "KYC start → KYC completed",
    "decision_made": "KYC completed → credit decision",
    "loan_disbursed": "Credit decision → loan disbursed",
}


def write_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(ROOT / "outputs" / name, index=False, lineterminator="\n", float_format="%.10g")


def main() -> None:
    con = connect()
    for f in ("03_funnel_overall.sql", "04_funnel_segments.sql", "05_stage_timing.sql"):
        run_sql(con, f)
    overall = con.execute("SELECT * FROM funnel_overall ORDER BY stage_order").df()
    seg = con.execute("SELECT * FROM funnel_segments ORDER BY dim, segment, stage_order").df()
    timing = con.execute("SELECT * FROM stage_timing ORDER BY device, transition").df()
    cube = con.execute("SELECT * FROM funnel_cube ORDER BY ALL").df()
    con.close()

    # Wilson 95% CI for each stage-to-stage conversion within a segment.
    has_prev = seg["prev_users"].notna()
    lo, hi = proportion_confint(seg.loc[has_prev, "users"], seg.loc[has_prev, "prev_users"], 0.05, "wilson")
    seg["conversion_ci_low"], seg["conversion_ci_high"] = pd.NA, pd.NA
    seg.loc[has_prev, "conversion_ci_low"] = lo.to_numpy()
    seg.loc[has_prev, "conversion_ci_high"] = hi.to_numpy()
    for c in ("prev_users", "dropped", "dropoff_rank"):
        seg[c] = seg[c].astype("Int64")
    overall["prev_users"] = overall["prev_users"].astype("Int64")
    overall["dropped"] = overall["dropped"].astype("Int64")

    write_csv(overall, "funnel_overall.csv")
    write_csv(seg, "funnel_segments.csv")
    write_csv(timing, "stage_timing.csv")
    write_csv(cube, "funnel_cube.csv")

    steps = overall.dropna(subset=["dropped"])
    worst = steps.loc[steps["dropped"].idxmax()]
    lowest = steps.loc[steps["conversion_from_prev"].idxmin()]
    ranked = seg[seg["dropoff_rank"] == 1]
    agree = ranked[ranked["stage"] == worst["stage"]]
    write_json("outputs/funnel_summary.json", {
        "simulated": True,
        "period": "pre",
        "users_started": int(overall.iloc[0]["users"]),
        "users_disbursed": int(overall.iloc[-1]["users"]),
        "start_to_disbursal_conversion": float(overall.iloc[-1]["conversion_from_start"]),
        "total_dropped": int(steps["dropped"].sum()),
        "largest_dropoff": {
            "stage": worst["stage"],
            "transition": LABELS[worst["stage"]],
            "users_lost": int(worst["dropped"]),
            "dropoff_share": float(worst["dropoff_share"]),
            "conversion_from_prev": float(worst["conversion_from_prev"]),
            "users_entering": int(worst["prev_users"]),
        },
        "lowest_conversion": {
            "stage": lowest["stage"], "transition": LABELS[lowest["stage"]],
            "conversion_from_prev": float(lowest["conversion_from_prev"]),
        },
        "lenses_agree": bool(worst["stage"] == lowest["stage"]),
        "segments_where_largest_dropoff_is_same_stage": int(len(agree)),
        "segments_total": int(len(ranked)),
        "segments_where_it_differs": [f"{r.dim}={r.segment}: {LABELS[r.stage]}"
                                      for r in ranked[ranked["stage"] != worst["stage"]].itertuples()],
        "kyc_completion_rate_pre_period": {
            "definition": "users who completed KYC / users who started KYC (pre-period funnel denominator)",
            "value": float(overall.loc[overall["stage"] == "kyc_completed", "conversion_from_prev"].iloc[0]),
        },
        "stage_timing_all_devices": {r.transition: {"median_minutes": float(r.median_minutes),
                                                    "p90_minutes": float(r.p90_minutes), "users": int(r.users)}
                                     for r in timing[timing["device"] == "all"].itertuples()},
        "transitions": [{"stage": r.stage, "transition": LABELS[r.stage], "users_lost": int(r.dropped),
                         "dropoff_share": float(r.dropoff_share), "conversion_from_prev": float(r.conversion_from_prev)}
                        for r in steps.itertuples()],
    })
    print(overall.to_string(index=False))
    print("largest drop-off:", LABELS[worst["stage"]], f"share={worst['dropoff_share']:.3f}")


if __name__ == "__main__":
    main()
