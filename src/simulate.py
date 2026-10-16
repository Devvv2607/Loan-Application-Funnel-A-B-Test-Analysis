"""Phase 1: generate the simulated event log (users, events, loans).

Design choices that matter for the analysis:
  * An event log, not pre-aggregated flags, so the funnel is genuinely rebuilt in SQL.
  * Randomization happens at the user's first kyc_started in the experiment period,
    by a seeded hash of user_id, so the experiment population is exactly "users who
    reached KYC" and assignment is reproducible without any RNG state.
  * Potential outcomes for KYC: one uniform draw u per user; the user completes under
    control if u < p_c and under treatment if u < p_t. Users with p_c <= u < p_t are
    "marginal" applicants who finish only because KYC got simpler, and they carry
    worse approval and delinquency odds (the selection effect the guardrails must catch).
  * Every random stream is drawn for ALL users up front in a fixed order, so one
    parameter change does not reshuffle unrelated draws.
  * Data-quality issues are injected after the clean log is built, and their exact
    counts are written to outputs/injected_issues.json so cleaning can be checked.
"""

from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd

from common import ROOT, settings, sim_config, write_json
from model import (SEGMENT_DIMS, kyc_complete_probs, randomized_population_expectations, segment_cells,
                   stage_prob, weekend_share)

EVENT_ORDER = ["application_started", "kyc_started", "kyc_completed", "decision_made", "loan_disbursed"]
STAGE_INDEX = {e: i for i, e in enumerate(EVENT_ORDER)}


def hash_unit(seed: int, user_id: str) -> float:
    """Deterministic uniform in [0, 1) from seed and user_id."""
    h = hashlib.sha256(f"{seed}:{user_id}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def assign_variant(seed: int, user_id: str) -> str:
    return "treatment" if hash_unit(seed, user_id) < 0.5 else "control"


def _lognormal_seconds(rng, n, spec: dict, unit: float = 60.0) -> np.ndarray:
    return np.round(rng.lognormal(np.log(spec["median"] * unit), spec["sigma"], n)).astype(np.int64)


def _draw_categorical(rng, n, mix: dict) -> np.ndarray:
    levels = [str(k) for k in mix]
    return rng.choice(np.array(levels, dtype=object), size=n, p=np.array(list(mix.values()), dtype=float))


def _prob_array(cfg, users: pd.DataFrame, fn) -> np.ndarray:
    """Evaluate fn(seg, weekend) once per unique cell and broadcast to users."""
    out = np.empty(len(users))
    for key, idx in users.groupby(SEGMENT_DIMS + ["weekend"], sort=True).indices.items():
        seg = dict(zip(SEGMENT_DIMS, key[:3]))
        out[idx] = fn(seg, bool(key[3]))
    return out


def generate(seed: int, broken: bool = False) -> dict:
    s, cfg = settings(), sim_config()
    rng = np.random.default_rng(seed)
    per = s["periods"]
    pre_days = 7 * per["pre_period_weeks"]
    total_days = pre_days + 7 * per["experiment_weeks"]
    n = cfg["population"]["total_users"]
    start = pd.Timestamp(per["start_date"])
    start_epoch = int(start.timestamp())

    # --- users, traffic by day with day-of-week seasonality ---
    dow_w = np.array(cfg["population"]["dow_traffic_weights"], dtype=float)
    day_w = np.tile(dow_w, total_days // 7)
    per_day = rng.multinomial(n, day_w / day_w.sum())
    day = np.repeat(np.arange(total_days), per_day)
    sec_in_day = np.clip(rng.normal(14 * 3600, 4.5 * 3600, n), 0, 86399).astype(np.int64)
    signup = start_epoch + day * 86400 + sec_in_day
    order = np.argsort(signup, kind="stable")
    day, signup = day[order], signup[order]

    users = pd.DataFrame({
        "user_id": [f"U{i:06d}" for i in range(1, n + 1)],
        "signup_epoch": signup,
        "device": _draw_categorical(rng, n, cfg["segment_mix"]["device"]),
        "channel": _draw_categorical(rng, n, cfg["segment_mix"]["channel"]),
        "city_tier": _draw_categorical(rng, n, cfg["segment_mix"]["city_tier"]),
    })
    users["weekend"] = (day % 7) >= 5
    users["period"] = np.where(day < pre_days, "pre", "experiment")

    # --- all random streams, drawn up front in a fixed order ---
    u_kyc_start, u_kyc_complete, u_decision, u_approve, u_disburse, u_dpd, u_retry, u_retry2 = (
        rng.random(n) for _ in range(8))
    t = cfg["timing"]
    gap_app = _lognormal_seconds(rng, n, t["signup_to_application_minutes"])
    gap_kyc = _lognormal_seconds(rng, n, t["application_to_kyc_start_minutes"])
    gap_complete = _lognormal_seconds(rng, n, t["kyc_start_to_complete_minutes"])
    gap_decision = _lognormal_seconds(rng, n, t["kyc_complete_to_decision_minutes"])
    gap_disburse = _lognormal_seconds(rng, n, t["decision_to_disbursal_minutes"])
    r = cfg["retries"]
    retry_spec = {"median": r["retry_gap_minutes_median"], "sigma": r["retry_gap_sigma"]}
    min_gap = r["retry_gap_minutes_min"] * 60
    retry_gap1 = np.maximum(_lognormal_seconds(rng, n, retry_spec), min_gap)
    retry_gap2 = np.maximum(_lognormal_seconds(rng, n, retry_spec), min_gap)
    amounts = np.round(rng.lognormal(np.log(cfg["loans"]["amount_median"]), cfg["loans"]["amount_sigma"], n), -2)

    # --- stage probabilities per user ---
    p_start = _prob_array(cfg, users, lambda sg, we: stage_prob(cfg, "kyc_started", sg, we))
    p_c = _prob_array(cfg, users, lambda sg, we: kyc_complete_probs(cfg, sg, we)[0])
    p_t = _prob_array(cfg, users, lambda sg, we: kyc_complete_probs(cfg, sg, we)[1])
    p_dec = _prob_array(cfg, users, lambda sg, we: stage_prob(cfg, "decision_made", sg, we))
    p_app = _prob_array(cfg, users, lambda sg, we: stage_prob(cfg, "approved", sg, we))
    p_app_m = _prob_array(cfg, users, lambda sg, we: stage_prob(cfg, "approved", sg, we, True))
    p_dis = _prob_array(cfg, users, lambda sg, we: stage_prob(cfg, "loan_disbursed", sg, we))
    p_dpd = _prob_array(cfg, users, lambda sg, we: stage_prob(cfg, "dpd30_first_emi", sg, we))
    p_dpd_m = _prob_array(cfg, users, lambda sg, we: stage_prob(cfg, "dpd30_first_emi", sg, we, True))

    # --- progression ---
    app_ts = users["signup_epoch"].to_numpy() + gap_app
    started = u_kyc_start < p_start
    kyc_ts = app_ts + gap_kyc
    n_retries = np.where(started & (u_retry < r["kyc_retry_prob"]),
                         1 + (u_retry2 < r["second_retry_prob"]).astype(int), 0)
    retry1_ts = kyc_ts + retry_gap1
    retry2_ts = retry1_ts + retry_gap2
    last_kyc_ts = np.where(n_retries == 2, retry2_ts, np.where(n_retries == 1, retry1_ts, kyc_ts))

    randomized = started & (users["period"].to_numpy() == "experiment")
    variant = np.array([assign_variant(seed, uid) if rz else None
                        for uid, rz in zip(users["user_id"], randomized)], dtype=object)
    if broken:
        # Assignment bug: a bot filter applied to the treatment arm only drops some
        # treatment users from the assignment log (they vanish from the experiment).
        drop = (variant == "treatment") & (rng.random(n) < cfg["broken_experiment"]["treatment_bot_filter_drop_rate"])
        variant[drop] = None
        randomized = randomized & ~drop
    is_t = variant == "treatment"
    p_complete = np.where(is_t, p_t, p_c)
    completed = started & (u_kyc_complete < p_complete)
    marginal = is_t & completed & (u_kyc_complete >= p_c)
    dur_mult = np.where(is_t, cfg["treatment"]["kyc_duration_multiplier"], 1.0)
    complete_ts = last_kyc_ts + np.round(gap_complete * dur_mult).astype(np.int64)
    decided = completed & (u_decision < p_dec)
    decision_ts = complete_ts + gap_decision
    approved = decided & (u_approve < np.where(marginal, p_app_m, p_app))
    disbursed = approved & (u_disburse < p_dis)
    disburse_ts = decision_ts + gap_disburse
    dpd = disbursed & (u_dpd < np.where(marginal, p_dpd_m, p_dpd))

    users["variant"] = variant
    users["assigned_epoch"] = np.where(randomized, kyc_ts, -1)

    # --- events (clean log) ---
    uid = users["user_id"].to_numpy()
    parts = [pd.DataFrame({"user_id": uid, "event_name": "application_started", "event_epoch": app_ts})]
    parts.append(pd.DataFrame({"user_id": uid[started], "event_name": "kyc_started", "event_epoch": kyc_ts[started]}))
    m1, m2 = n_retries >= 1, n_retries >= 2
    parts.append(pd.DataFrame({"user_id": uid[m1], "event_name": "kyc_started", "event_epoch": retry1_ts[m1],
                               "is_retry": True}))
    parts.append(pd.DataFrame({"user_id": uid[m2], "event_name": "kyc_started", "event_epoch": retry2_ts[m2],
                               "is_retry": True}))
    parts.append(pd.DataFrame({"user_id": uid[completed], "event_name": "kyc_completed",
                               "event_epoch": complete_ts[completed]}))
    parts.append(pd.DataFrame({"user_id": uid[decided], "event_name": "decision_made",
                               "event_epoch": decision_ts[decided],
                               "decision_outcome": np.where(approved[decided], "approved", "declined")}))
    parts.append(pd.DataFrame({"user_id": uid[disbursed], "event_name": "loan_disbursed",
                               "event_epoch": disburse_ts[disbursed]}))
    ev = pd.concat(parts, ignore_index=True)
    ev["is_retry"] = ev["is_retry"].astype("boolean").fillna(False).astype(bool)
    ev["is_dup"] = False
    ev["stage"] = ev["event_name"].map(STAGE_INDEX)

    # --- inject data-quality issues ---
    dq = cfg["data_quality"]
    # 1) missing preceding stage: drop an intermediate stage's events for a few users.
    #    The user must keep a LATER stage event, otherwise the gap is indistinguishable
    #    from genuine abandonment: drop kyc_started only if kyc_completed exists, and
    #    decision_made only if loan_disbursed exists.
    eligible = uid[completed]
    miss_users = rng.choice(eligible, size=dq["missing_step_users"], replace=False)
    miss_set = set(miss_users)
    has_disbursal = set(uid[disbursed])
    miss_stage = {}
    for u in sorted(miss_set):
        miss_stage[u] = "decision_made" if (u in has_disbursal and rng.random() < 0.5) else "kyc_started"
    drop_mask = np.array([miss_stage.get(u) == e for u, e in zip(ev["user_id"], ev["event_name"])])
    dropped_missing = int(drop_mask.sum())
    ev = ev[~drop_mask].reset_index(drop=True)

    # 2) out-of-order: shift one first-of-stage event per user before its preceding stage.
    first_ts = ev[~ev["is_retry"]].pivot_table(index="user_id", columns="event_name", values="event_epoch",
                                                aggfunc="min")
    cand = ev.index[(ev["stage"] >= 1) & ~ev["is_retry"] & ~ev["user_id"].isin(miss_set)].to_numpy()
    n_ooo = int(round(dq["out_of_order_rate"] * len(ev)))
    cand = cand[rng.permutation(len(cand))]
    chosen, seen = [], set()
    for i in cand:
        u = ev.at[i, "user_id"]
        if u in seen:
            continue
        seen.add(u)
        chosen.append(i)
        if len(chosen) == n_ooo:
            break
    chosen = np.array(sorted(chosen))
    ooo_names = [EVENT_ORDER[ev.at[i, "stage"]] for i in chosen]
    prev_names = [EVENT_ORDER[ev.at[i, "stage"] - 1] for i in chosen]
    prev_ts = np.array([first_ts.at[ev.at[i, "user_id"], p] for i, p in zip(chosen, prev_names)], dtype=np.int64)
    ev.loc[chosen, "event_epoch"] = prev_ts - rng.integers(60, 3600, len(chosen))
    ev["is_ooo"] = False
    ev.loc[chosen, "is_ooo"] = True

    # 3) duplicates: re-emit ~1% of events within a few seconds.
    n_dup = int(round(dq["duplicate_event_rate"] * len(ev)))
    dup_idx = np.sort(rng.choice(len(ev), size=n_dup, replace=False))
    dups = ev.iloc[dup_idx].copy()
    dups["event_epoch"] = dups["event_epoch"] + rng.integers(0, dq["duplicate_max_offset_seconds"] + 1, n_dup)
    dups["is_dup"] = True
    ev = pd.concat([ev, dups], ignore_index=True)

    # 4) null device on a few users (user-agent parse failures).
    n_null = int(round(dq["null_device_rate"] * n))
    null_idx = np.sort(rng.choice(n, size=n_null, replace=False))
    users.loc[null_idx, "device"] = None

    ev = ev.sort_values(["event_epoch", "user_id", "stage", "is_dup"], kind="stable").reset_index(drop=True)
    ev["event_id"] = [f"E{i:07d}" for i in range(1, len(ev) + 1)]

    loans = pd.DataFrame({"user_id": uid[disbursed], "disbursed_epoch": disburse_ts[disbursed],
                          "amount": amounts[disbursed], "dpd_30_on_first_emi": dpd[disbursed].astype(int)})
    loans["first_emi_due_epoch"] = loans["disbursed_epoch"] + cfg["loans"]["first_emi_due_days"] * 86400
    loans = loans.sort_values(["disbursed_epoch", "user_id"]).reset_index(drop=True)
    loans["loan_id"] = [f"L{i:06d}" for i in range(1, len(loans) + 1)]

    retries_kept = int((ev["is_retry"] & ~ev["is_dup"]).sum())
    return {
        "users": users, "events": ev, "loans": loans,
        "meta": {
            "n_randomized": int(randomized.sum()), "n_treatment": int(is_t.sum()),
            "n_marginal": int(marginal.sum()), "retries_kept": retries_kept,
            "injected": {
                "duplicate_events": n_dup,
                "out_of_order_events": int(len(chosen)),
                "out_of_order_by_stage": _count_by(ooo_names),
                "null_device_users": n_null,
                "missing_step_users": len(miss_set),
                "missing_step_by_stage": _count_by(list(miss_stage.values())),
                "missing_step_events_dropped": dropped_missing,
            },
        },
    }


def _count_by(items) -> dict:
    out: dict = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def _fmt_ts(epoch: pd.Series) -> pd.Series:
    return pd.to_datetime(epoch, unit="s").dt.strftime("%Y-%m-%d %H:%M:%S")


def write_raw(out: dict, dest) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    u = out["users"].copy()
    u["signup_ts"] = _fmt_ts(u["signup_epoch"])
    u["assigned_ts"] = np.where(u["assigned_epoch"] >= 0, _fmt_ts(u["assigned_epoch"].clip(lower=0)), None)
    u[["user_id", "signup_ts", "device", "channel", "city_tier", "period", "variant", "assigned_ts"]].to_csv(
        dest / "users.csv", index=False, lineterminator="\n")
    e = out["events"].copy()
    e["event_ts"] = _fmt_ts(e["event_epoch"])
    if "decision_outcome" not in e:
        e["decision_outcome"] = None
    e[["event_id", "user_id", "event_name", "event_ts", "decision_outcome"]].to_csv(
        dest / "events.csv", index=False, lineterminator="\n")
    lo = out["loans"].copy()
    lo["disbursed_ts"] = _fmt_ts(lo["disbursed_epoch"])
    lo["first_emi_due_ts"] = _fmt_ts(lo["first_emi_due_epoch"])
    lo[["loan_id", "user_id", "disbursed_ts", "amount", "first_emi_due_ts", "dpd_30_on_first_emi"]].to_csv(
        dest / "loans.csv", index=False, lineterminator="\n", float_format="%.0f")


def ground_truth(meta: dict) -> dict:
    """True (population-expected) quantities from the generating model."""
    s, cfg = settings(), sim_config()
    ws = weekend_share(cfg)
    names = ["kyc_started", "kyc_completed", "decision_made", "approved", "loan_disbursed", "dpd30_first_emi"]

    def expected_stage_rates(filter_seg=None):
        num = {k: 0.0 for k in names}
        den = 0.0
        for seg, w in segment_cells(cfg):
            if filter_seg and any(seg[d] != v for d, v in filter_seg.items()):
                continue
            for we, sh in ((False, 1 - ws), (True, ws)):
                cw = w * sh
                den += cw
                p = 1.0
                for k in names:
                    p *= stage_prob(cfg, k, seg, we)
                    num[k] += cw * p
        reach = {k: num[k] / den for k in names}
        cond = {}
        prev = 1.0
        for k in names:
            cond[k] = reach[k] / prev
            prev = reach[k]
        return {"reach_share_of_applicants": reach, "stage_to_stage_conversion": cond}

    def effects(filter_seg=None):
        e = randomized_population_expectations(cfg, filter_seg)
        c, t = e["control"], e["treatment"]
        return {
            "kyc_completion_control": c["kyc_completed"], "kyc_completion_treatment": t["kyc_completed"],
            "kyc_completion_diff_pp": (t["kyc_completed"] - c["kyc_completed"]) * 100,
            "kyc_completion_relative_lift": t["kyc_completed"] / c["kyc_completed"] - 1,
            "disbursal_share_diff_pp": (t["loans"] - c["loans"]) * 100,
            "delinquent_per_1000_diff": (t["delinquent"] - c["delinquent"]) * 1000,
            "early_delinquency_rate_diff_pp": (t["delinquent"] / t["loans"] - c["delinquent"] / c["loans"]) * 100,
            "approval_rate_diff_pp": (t["approvals"] / t["decisions"] - c["approvals"] / c["decisions"]) * 100,
        }

    by_segment = {}
    for dim in SEGMENT_DIMS:
        for level in cfg["segment_mix"][dim]:
            by_segment[f"{dim}={level}"] = effects({dim: str(level)})
    return {
        "simulated": True,
        "seed": s["seed"],
        "note": "Population-expected values from the generating model (src/model.py). "
                "Observed estimates differ by sampling noise.",
        "pre_period_funnel": expected_stage_rates(),
        "pre_period_funnel_by_segment": {f"{d}={lv}": expected_stage_rates({d: str(lv)})
                                         for d in SEGMENT_DIMS for lv in cfg["segment_mix"][d]},
        "treatment_effect": effects(),
        "treatment_effect_by_segment": by_segment,
        "realised": {
            "randomized_users": meta["n_randomized"],
            "treatment_users": meta["n_treatment"],
            "marginal_applicants_in_treatment": meta["n_marginal"],
            "legitimate_kyc_retries": meta["retries_kept"],
        },
    }


def main() -> None:
    seed = settings()["seed"]
    raw = ROOT / settings()["paths"]["raw_dir"]
    out = generate(seed)
    write_raw(out, raw)
    write_json("outputs/ground_truth.json", ground_truth(out["meta"]))
    write_json("outputs/injected_issues.json", {"simulated": True, "seed": seed, **out["meta"]["injected"],
                                                "legitimate_kyc_retries_present": out["meta"]["retries_kept"]})
    broken = generate(seed, broken=True)
    write_raw(broken, ROOT / settings()["paths"]["broken_dir"])
    m = out["meta"]
    print(f"users={len(out['users'])} events={len(out['events'])} loans={len(out['loans'])} "
          f"randomized={m['n_randomized']} treatment_share={m['n_treatment'] / m['n_randomized']:.4f} "
          f"retries={m['retries_kept']}")


if __name__ == "__main__":
    main()
