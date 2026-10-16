"""The data-generating probability model, shared by the simulator, the ground
truth and the feasibility check.

Keeping one implementation matters analytically: the "true" effects reported in
ground_truth.json and the expectations used for planning are exact expectations
of the same model the simulator samples from, so any gap between an estimate
and the truth is sampling noise (or an analysis bug), never a modelling mismatch.

Stage probabilities are built on the log-odds scale: reference-segment
probability + segment shifts + weekend shift (+ treatment / marginal shifts).
"""

from __future__ import annotations

import itertools
import math

STAGES = ["kyc_started", "kyc_completed", "decision_made", "approved", "loan_disbursed", "dpd30_first_emi"]
SEGMENT_DIMS = ["device", "channel", "city_tier"]


def logit(p: float) -> float:
    return math.log(p / (1 - p))


def expit(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def segment_cells(cfg: dict):
    """Yield (segment dict, population weight) for every device x channel x tier cell."""
    mix = cfg["segment_mix"]
    dims = [list(mix[d].items()) for d in SEGMENT_DIMS]
    for combo in itertools.product(*dims):
        seg = {d: str(level) for d, (level, _) in zip(SEGMENT_DIMS, combo)}
        w = math.prod(share for _, share in combo)
        yield seg, w


def weekend_share(cfg: dict) -> float:
    w = cfg["population"]["dow_traffic_weights"]
    return (w[5] + w[6]) / sum(w)


def stage_logit(cfg: dict, stage: str, seg: dict, weekend: bool) -> float:
    x = logit(cfg["stages"][stage])
    for dim in SEGMENT_DIMS:
        x += cfg["segment_effects"].get(dim, {}).get(seg[dim], {}).get(stage, 0.0)
    if weekend:
        x += cfg["seasonality"]["weekend_logit_shift"].get(stage, 0.0)
    return x


def stage_prob(cfg: dict, stage: str, seg: dict, weekend: bool, marginal: bool = False) -> float:
    x = stage_logit(cfg, stage, seg, weekend)
    if marginal:
        x += cfg["treatment"]["marginal_logit_shift"].get(stage, 0.0)
    return expit(x)


def treatment_shift(cfg: dict, seg: dict) -> float:
    t = cfg["treatment"]
    shift = t["kyc_completed_logit_shift"]
    for dim, mods in t["segment_logit_shift_modifiers"].items():
        shift += mods.get(seg[dim], 0.0)
    return shift


def kyc_complete_probs(cfg: dict, seg: dict, weekend: bool) -> tuple[float, float]:
    """(control, treatment) KYC completion probability for one randomized user.

    Potential-outcomes structure: a user with latent u completes under control if
    u < p_c and under treatment if u < p_t. Users with p_c <= u < p_t are the
    "marginal" applicants who finish only because KYC got simpler.
    """
    base = stage_logit(cfg, "kyc_completed", seg, weekend)
    return expit(base), expit(base + treatment_shift(cfg, seg))


def per_randomized_user_expectations(cfg: dict, seg: dict, weekend: bool) -> dict:
    """Expected per-randomized-user outcomes in each arm for one segment cell."""
    pc, pt = kyc_complete_probs(cfg, seg, weekend)
    pdec = stage_prob(cfg, "decision_made", seg, weekend)
    pa, pa_m = stage_prob(cfg, "approved", seg, weekend), stage_prob(cfg, "approved", seg, weekend, True)
    pdis = stage_prob(cfg, "loan_disbursed", seg, weekend)
    pdq, pdq_m = (stage_prob(cfg, "dpd30_first_emi", seg, weekend),
                  stage_prob(cfg, "dpd30_first_emi", seg, weekend, True))
    out = {}
    for arm, p_complete in (("control", pc), ("treatment", pt)):
        regular, marginal = pc, p_complete - pc
        decisions = (regular + marginal) * pdec
        approvals = regular * pdec * pa + marginal * pdec * pa_m
        loans = regular * pdec * pa * pdis + marginal * pdec * pa_m * pdis
        delinquent = regular * pdec * pa * pdis * pdq + marginal * pdec * pa_m * pdis * pdq_m
        out[arm] = {"kyc_completed": p_complete, "decisions": decisions, "approvals": approvals,
                    "loans": loans, "delinquent": delinquent}
    return out


def randomized_population_expectations(cfg: dict, filter_seg: dict | None = None) -> dict:
    """Expected per-randomized-user outcomes averaged over the randomized population.

    The randomized population is users who START KYC, so each cell is weighted by
    its traffic share x its KYC-start probability (composition differs from signups).
    `filter_seg` restricts to cells matching e.g. {"device": "web"}.
    """
    ws = weekend_share(cfg)
    totals = {arm: {k: 0.0 for k in ("kyc_completed", "decisions", "approvals", "loans", "delinquent")}
              for arm in ("control", "treatment")}
    total_w = 0.0
    for seg, w in segment_cells(cfg):
        if filter_seg and any(seg[d] != str(v) for d, v in filter_seg.items()):
            continue
        for weekend, share in ((False, 1 - ws), (True, ws)):
            cell_w = w * share * stage_prob(cfg, "kyc_started", seg, weekend)
            total_w += cell_w
            e = per_randomized_user_expectations(cfg, seg, weekend)
            for arm in totals:
                for k in totals[arm]:
                    totals[arm][k] += cell_w * e[arm][k]
    for arm in totals:
        for k in totals[arm]:
            totals[arm][k] /= total_w
    return totals


def expected_kyc_start_share(cfg: dict) -> float:
    ws = weekend_share(cfg)
    return sum(w * ((1 - ws) * stage_prob(cfg, "kyc_started", seg, False)
                    + ws * stage_prob(cfg, "kyc_started", seg, True))
               for seg, w in segment_cells(cfg))
