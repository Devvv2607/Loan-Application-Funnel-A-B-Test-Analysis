"""Phase 8: validate the METHOD by simulation, not just this one dataset.

A single experiment that recovers the truth could be luck. These checks show
the analysis behaves as advertised over many replications:
  * A/A: with no true effect, the z-test rejects ~5% of the time (alpha).
  * CI coverage: with the planted effect, ~95% of Newcombe 95% CIs contain it.
  * SRM: the chi-square check flags the deliberately broken dataset (bot filter
    on one arm) and passes the main dataset.
  * Peeking: checking an A/A test every day and stopping at the first p < 0.05
    inflates the false-positive rate well above the fixed-horizon 5%.

Replications draw from the same generating model as the main data (src/model.py):
users are sampled across segment x weekend cells with the randomized-population
weights, randomized 50/50, and outcomes drawn per cell. That keeps segment
heterogeneity in the replications without re-running the full event generator.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from abstats import newcombe_diff_ci, srm_chisquare, ztest_two_proportions
from common import ROOT, read_json, settings, sim_config, write_json
from model import kyc_complete_probs, segment_cells, stage_prob, weekend_share


def cell_table(cfg: dict) -> pd.DataFrame:
    ws = weekend_share(cfg)
    rows = []
    for seg, w in segment_cells(cfg):
        for we, sh in ((False, 1 - ws), (True, ws)):
            pc, pt = kyc_complete_probs(cfg, seg, we)
            rows.append({"w": w * sh * stage_prob(cfg, "kyc_started", seg, we), "pc": pc, "pt": pt})
    df = pd.DataFrame(rows)
    df["w"] /= df["w"].sum()
    return df


def replicate(rng, cells: pd.DataFrame, n_total: int, effect: bool) -> tuple[int, int, int, int]:
    n_k = rng.multinomial(n_total, cells["w"].to_numpy())
    n_t = rng.binomial(n_k, 0.5)
    n_c = n_k - n_t
    x_c = rng.binomial(n_c, cells["pc"].to_numpy())
    x_t = rng.binomial(n_t, (cells["pt"] if effect else cells["pc"]).to_numpy())
    return int(x_c.sum()), int(n_c.sum()), int(x_t.sum()), int(n_t.sum())


def main() -> None:
    s, cfg = settings(), sim_config()
    rng = np.random.default_rng(s["seed"])
    cells = cell_table(cfg)
    res = read_json("outputs/experiment_results.json")
    n_total = sum(res["assignment_counts"].values())
    alpha = res["alpha"]
    truth = read_json("outputs/ground_truth.json")["treatment_effect"]["kyc_completion_diff_pp"] / 100

    # A/A false-positive rate.
    n_aa = 1000
    rej = 0
    for _ in range(n_aa):
        xc, nc, xt, nt = replicate(rng, cells, n_total, effect=False)
        rej += ztest_two_proportions(xc, nc, xt, nt)[1] < alpha
    fpr = rej / n_aa

    # CI coverage under the planted effect.
    n_cov = 500
    covered = 0
    for _ in range(n_cov):
        xc, nc, xt, nt = replicate(rng, cells, n_total, effect=True)
        lo, hi = newcombe_diff_ci(xc, nc, xt, nt, alpha)
        covered += lo <= truth <= hi
    coverage = covered / n_cov

    # SRM on the broken dataset vs the main dataset.
    broken = pd.read_csv(ROOT / s["paths"]["broken_dir"] / "users.csv")["variant"].value_counts()
    b_counts = [int(broken.get("control", 0)), int(broken.get("treatment", 0))]
    b_stat, b_p = srm_chisquare(b_counts, [0.5, 0.5])
    main_srm = read_json("outputs/srm.json")

    # Peeking: daily looks at an A/A test, stop at first p < alpha.
    days = 7 * s["periods"]["experiment_weeks"]
    dow = np.tile(np.array(cfg["population"]["dow_traffic_weights"], dtype=float), days // 7)
    p_bar = float((cells["w"] * cells["pc"]).sum())
    n_peek = 1000
    peek_rej = fixed_rej = 0
    for _ in range(n_peek):
        per_day = rng.multinomial(n_total, dow / dow.sum())
        nt_d = rng.binomial(per_day, 0.5)
        nc_d = per_day - nt_d
        xc_d, xt_d = rng.binomial(nc_d, p_bar), rng.binomial(nt_d, p_bar)
        cxc, cnc, cxt, cnt = np.cumsum(xc_d), np.cumsum(nc_d), np.cumsum(xt_d), np.cumsum(nt_d)
        ps = [ztest_two_proportions(int(a), int(b), int(c), int(d))[1] for a, b, c, d in zip(cxc, cnc, cxt, cnt)]
        peek_rej += any(p < alpha for p in ps)
        fixed_rej += ps[-1] < alpha

    write_json("outputs/validation_sims.json", {
        "simulated": True,
        "seed": s["seed"],
        "users_per_replication": n_total,
        "aa_test": {"replications": n_aa, "false_positive_rate": fpr, "expected": alpha,
                    "acceptance_range": [0.035, 0.065], "passed": 0.035 <= fpr <= 0.065},
        "ci_coverage": {"replications": n_cov, "true_effect_pp": truth * 100, "coverage": coverage,
                        "expected": 1 - alpha, "acceptance_range": [0.92, 0.98], "passed": 0.92 <= coverage <= 0.98},
        "srm_detection": {
            "broken_dataset": {"bug": "bot filter applied to the treatment arm only", "counts": {
                "control": b_counts[0], "treatment": b_counts[1]},
                "treatment_share": b_counts[1] / sum(b_counts), "chi2": b_stat, "p_value": b_p,
                "flagged": b_p < 0.001},
            "main_dataset": {"p_value": main_srm["p_value"], "flagged": not main_srm["passed"]},
            "passed": b_p < 0.001 and main_srm["passed"],
        },
        "peeking": {"replications": n_peek, "looks": days, "rule": "stop at the first daily look with p < 0.05",
                    "false_positive_rate_peeking": peek_rej / n_peek,
                    "false_positive_rate_fixed_horizon": fixed_rej / n_peek,
                    "inflation_factor": (peek_rej / n_peek) / max(fixed_rej / n_peek, 1e-9),
                    "passed": peek_rej > fixed_rej},
    })
    print(f"A/A FPR={fpr:.3f}  coverage={coverage:.3f}  broken SRM p={b_p:.2e} share={b_counts[1] / sum(b_counts):.3f}"
          f"  peeking={peek_rej / n_peek:.3f} vs fixed={fixed_rej / n_peek:.3f}")


if __name__ == "__main__":
    main()
