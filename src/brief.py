"""Write and freeze the pre-registration (config/experiment_brief.yaml).

Run once, before any data is simulated. The decision-guardrail margin is a
break-even calculation from inputs that exist independently of the planted
treatment and selection effects:
  * the pre-registered business MDE (3pp KYC completion lift);
  * control-arm baseline rates implied by simulation.yaml (KYC completed ->
    decision -> approval -> disbursal), computed with the `treatment` block
    removed from the config so the planted effects cannot leak in;
  * unit economics: profit on a good loan and loss on an early-delinquent loan.

Break-even: if the treatment adds dL loans and dD early-delinquent loans per
1,000 randomized users, the change in profit is dL*g - dD*(g + l), where g is
the profit on a good loan and l the loss on a delinquent one (a delinquent loan
both forgoes g and loses l). Profit stays >= 0 while dD <= dL * g / (g + l).
At the business MDE, dL = MDE x P(loan | KYC completed, control) x 1,000.

Once written, the file's SHA-256 is recorded in outputs/brief_freeze.json and
the script refuses to overwrite it.
"""

from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone

from common import ROOT, settings, sim_config, write_json
from model import SEGMENT_DIMS, segment_cells, stage_prob, weekend_share

BRIEF = ROOT / "config" / "experiment_brief.yaml"


def control_baseline_rates(cfg: dict) -> dict:
    """Control-arm conversion rates among KYC completers, weighted over the randomized population.

    Uses only control-path stage probabilities. The caller passes a config with
    the treatment block deleted, so any accidental use of it raises KeyError.
    """
    ws = weekend_share(cfg)
    acc = {"kyc_completed": 0.0, "decisions": 0.0, "approvals": 0.0, "loans": 0.0, "w": 0.0}
    for seg, w in segment_cells(cfg):
        for weekend, share in ((False, 1 - ws), (True, ws)):
            cw = w * share * stage_prob(cfg, "kyc_started", seg, weekend)
            pk = stage_prob(cfg, "kyc_completed", seg, weekend)
            pdec = pk * stage_prob(cfg, "decision_made", seg, weekend)
            pa = pdec * stage_prob(cfg, "approved", seg, weekend)
            pl = pa * stage_prob(cfg, "loan_disbursed", seg, weekend)
            acc["w"] += cw
            acc["kyc_completed"] += cw * pk
            acc["decisions"] += cw * pdec
            acc["approvals"] += cw * pa
            acc["loans"] += cw * pl
    k = acc["kyc_completed"]
    return {
        "kyc_completion_rate": k / acc["w"],
        "decision_given_kyc_completed": acc["decisions"] / k,
        "approval_given_decision": acc["approvals"] / acc["decisions"],
        "disbursal_given_approval": acc["loans"] / acc["approvals"],
        "loan_given_kyc_completed": acc["loans"] / k,
    }


def derive_margin() -> dict:
    s = settings()
    cfg = copy.deepcopy(sim_config())
    del cfg["treatment"]  # guarantee: the planted effects cannot enter the margin
    assert set(SEGMENT_DIMS) <= set(cfg["segment_mix"])
    base = control_baseline_rates(cfg)
    ue = s["unit_economics"]
    mde = s["feasibility_plan"]["business_mde_pp"] / 100
    g = ue["avg_loan_amount"] * ue["net_profit_good_loan_pct"] / 100
    loss = ue["avg_loan_amount"] * ue["loss_early_delinquent_loan_pct"] / 100
    extra_loans = mde * base["loan_given_kyc_completed"] * 1000
    margin = extra_loans * g / (g + loss)
    return {"baseline": base, "business_mde_pp": mde * 100, "profit_good_loan": g,
            "loss_delinquent_loan": loss, "extra_loans_per_1000_at_mde": extra_loans,
            "break_even_share": g / (g + loss), "margin": round(margin, 2)}


def render(m: dict, s: dict) -> str:
    b, ue, fp = m["baseline"], s["unit_economics"], s["feasibility_plan"]
    gm = fp["guardrail_margins"]
    return f"""# PRE-REGISTRATION: simplified-KYC experiment (Pebble Credit, fictional; all data simulated).
# Written by src/brief.py on {datetime.now(timezone.utc).strftime('%Y-%m-%d')} BEFORE any data was simulated.
# Frozen: the SHA-256 is in outputs/brief_freeze.json and checked before every analysis step.
# Nothing in this file may change after results are seen.

hypothesis: >-
  Replacing the current document-heavy KYC flow with a simplified flow increases the
  KYC completion rate of applicants who reach KYC, without an unacceptable increase in
  early-delinquent loans.

unit_of_randomization: user, assigned 50/50 by seeded hash of user_id at their first kyc_started event in the experiment period
analysis_population: intention-to-treat; every randomized user counts in their assigned arm for every metric
experiment_weeks: {s['periods']['experiment_weeks']}

primary_metric:
  name: KYC completion rate
  numerator: randomized users who complete KYC
  denominator: all users randomized into that arm at KYC start
  test: two-proportion z-test, two-sided
  alpha: {fp['alpha']}
  power: {fp['power']}
  mde_pp: {fp['business_mde_pp']}
  mde_rationale: >-
    A 3pp gain is the smallest lift that justifies the engineering, vendor and compliance
    cost of maintaining a second KYC flow.

secondary_metrics:
  - name: disbursal share of randomized users
    numerator: randomized users with a disbursed loan
    denominator: all users randomized into that arm at KYC start
    purpose: does the KYC gain survive the credit decision and offer acceptance?

guardrails:
  delinquent_per_1000_randomized:
    role: decision
    name: early-delinquent loans per 1,000 randomized users
    numerator: disbursed loans 30+ days past due on the first EMI
    denominator: all users randomized into that arm at KYC start (x 1,000)
    direction: higher_is_worse
    margin: {m['margin']}
    margin_unit: early-delinquent loans per 1,000 randomized users
    margin_derivation:
      formula: "margin = MDE x P(loan | KYC completed, control) x 1000 x g / (g + l)"
      inputs:
        business_mde_pp: {m['business_mde_pp']}
        control_decision_given_kyc_completed: {b['decision_given_kyc_completed']:.6f}
        control_approval_given_decision: {b['approval_given_decision']:.6f}
        control_disbursal_given_approval: {b['disbursal_given_approval']:.6f}
        control_loan_given_kyc_completed: {b['loan_given_kyc_completed']:.6f}
        avg_loan_amount: {ue['avg_loan_amount']}
        net_profit_good_loan_pct: {ue['net_profit_good_loan_pct']}
        loss_early_delinquent_loan_pct: {ue['loss_early_delinquent_loan_pct']}
        g_profit_per_good_loan: {m['profit_good_loan']:.2f}
        l_loss_per_delinquent_loan: {m['loss_delinquent_loan']:.2f}
      extra_loans_per_1000_at_mde: {m['extra_loans_per_1000_at_mde']:.4f}
      break_even_share_of_extra_loans: {m['break_even_share']:.6f}
      source_of_baseline_rates: control-path parameters in simulation.yaml (treatment block excluded)
    margin_rationale: >-
      At the 3pp business MDE, the simpler flow adds about {m['extra_loans_per_1000_at_mde']:.1f} disbursed loans
      per 1,000 randomized users. Each early-delinquent loan forgoes the profit of a good loan
      and loses about {ue['loss_early_delinquent_loan_pct']:.0f}% of principal, so the extra loans stay profitable
      only while no more than {m['break_even_share']:.1%} of them go early-delinquent. The margin is
      that break-even count. Note the per-user count rises mechanically with conversion:
      more loans means more delinquent loans even at an unchanged per-loan rate.
  early_delinquency_rate:
    role: diagnostic
    name: early delinquency rate among disbursed loans
    numerator: disbursed loans 30+ days past due on the first EMI
    denominator: disbursed loans in that arm (post-randomization; not a randomized comparison)
    direction: higher_is_worse
    margin_pp: {gm['early_delinquency_rate_pp']}
    margin_rationale: >-
      Roughly a quarter of the ~6% baseline; beyond this the credit policy team would re-price.
      Diagnostic only: the treatment changes who gets a loan, so arms hold different borrower mixes.
  approval_rate:
    role: diagnostic
    name: approval rate among credit decisions
    numerator: approved decisions
    denominator: credit decisions in that arm (post-randomization; not a randomized comparison)
    direction: lower_is_worse
    margin_pp: {gm['approval_rate_pp']}
    margin_rationale: >-
      A drop beyond 3pp would signal the simplified flow is filling the decision queue with
      applicants underwriting rejects, raising bureau and ops cost per loan. Diagnostic only.

guardrail_test: one-sided non-inferiority at alpha {fp['guardrail_alpha_one_sided']} (one-sided 95% confidence bound)
guardrail_pass_rule:
  pass: the one-sided 95% bound lies inside the margin
  fail: the point estimate lies beyond the margin
  inconclusive: the point estimate is inside the margin but the bound crosses it
  note: not statistically significant never means credit quality preserved

decision_rule:
  decision_guardrail: delinquent_per_1000_randomized
  ship: primary is significant (two-sided p < alpha) and positive AND the decision guardrail passes
  iterate: primary is significant and positive AND the decision guardrail fails or is inconclusive
  dont_ship: primary is not significant, or is significant and negative
  diagnostics: reported alongside the decision; they do not change it
"""


def main() -> None:
    if BRIEF.exists() and "decision_rule:" in BRIEF.read_text(encoding="utf-8"):
        raise SystemExit("experiment_brief.yaml is already frozen; refusing to overwrite.")
    s = settings()
    m = derive_margin()
    text = render(m, s)
    BRIEF.write_text(text, encoding="utf-8", newline="\n")
    write_json("outputs/brief_freeze.json", {
        "simulated": True,
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": hashlib.sha256(BRIEF.read_bytes()).hexdigest(),
        "decision_guardrail_margin": m["margin"],
        "derivation": m,
    })
    print(f"Frozen brief; decision-guardrail margin = {m['margin']} per 1,000 randomized users")


if __name__ == "__main__":
    main()
