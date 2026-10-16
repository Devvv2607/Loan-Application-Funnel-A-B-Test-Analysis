"""Phase 11: cross-stage consistency checks.

Each stage has its own tests; this script checks that the stages agree with
EACH OTHER: the manifest matches the files and tables, the funnel and
experiment tables agree with the SQL outputs, the same assignment counts appear
in every downstream artefact, the brief is unchanged, and every claim still
renders to the saved text. The website is only built if all checks pass.
"""

from __future__ import annotations

import hashlib
import sys

from claims import render_all
from common import ROOT, load_brief, read_json, settings, write_json
from ingest import connect


def main() -> None:
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    s = settings()
    man = read_json("outputs/data_manifest.json")
    con = connect(read_only=True)
    for fname, info in man["files"].items():
        p = ROOT / s["paths"]["raw_dir"] / fname
        check(f"manifest hash matches {fname}", hashlib.sha256(p.read_bytes()).hexdigest() == info["sha256"])
        n = con.execute(f"SELECT COUNT(*) FROM {info['table']}").fetchone()[0]
        check(f"manifest rows match table {info['table']}", n == info["rows"], f"{n} vs {info['rows']}")

    pre = con.execute("""SELECT SUM(reached_application_started::INT), SUM(reached_kyc_started::INT),
                                SUM(reached_kyc_completed::INT), SUM(reached_decision_made::INT),
                                SUM(reached_loan_disbursed::INT)
                         FROM user_stage_flags WHERE period = 'pre'""").fetchone()
    fo = con.execute("SELECT users FROM funnel_overall ORDER BY stage_order").fetchall()
    check("funnel_overall equals user_stage_flags (pre)", [r[0] for r in fo] == list(pre))
    import pandas as pd
    csv = pd.read_csv(ROOT / "outputs" / "funnel_overall.csv")
    check("funnel_overall.csv equals SQL table", csv["users"].tolist() == list(pre))
    fs = read_json("outputs/funnel_summary.json")
    check("funnel_summary start/end equal funnel counts", fs["users_started"] == pre[0] and
          fs["users_disbursed"] == pre[4])

    arm = {r[0]: r[1:] for r in con.execute("SELECT variant, randomized, kyc_completed, disbursed, early_delinquent "
                                            "FROM experiment_arm_metrics").fetchall()}
    exp_users = dict(con.execute("SELECT variant, COUNT(*) FROM users_clean WHERE variant IS NOT NULL "
                                 "GROUP BY 1").fetchall())
    con.close()
    res = read_json("outputs/experiment_results.json")
    counts = res["assignment_counts"]
    check("experiment tables equal assignment log", {k: v[0] for k, v in arm.items()} == counts == exp_users)
    check("primary numerators equal SQL", all(res["primary"][a]["numerator"] == arm[a][1] for a in counts))
    check("secondary numerators equal SQL", all(res["secondary"][a]["numerator"] == arm[a][2] for a in counts))
    grd = read_json("outputs/guardrails.json")
    ga = grd["guardrails"]["delinquent_per_1000_randomized"]
    check("decision guardrail numerators equal SQL", all(ga[a]["numerator"] == arm[a][3] for a in counts))

    others = {
        "srm.json": read_json("outputs/srm.json")["observed"],
        "guardrails.json": grd["assignment_counts"],
        "power_analysis.json": read_json("outputs/power_analysis.json")["experiment_assignment_counts"],
        "decision.json": read_json("outputs/decision.json")["assignment_counts"],
    }
    for name, c in others.items():
        check(f"assignment counts identical in {name}", c == counts, str(c))
    memo = (ROOT / s["paths"]["memo"]).read_text(encoding="utf-8")
    check("assignment counts identical in memo", f"{counts['control']:,} control" in memo and
          f"{counts['treatment']:,} treatment" in memo)

    try:
        load_brief()
        check("brief present and unchanged since freeze", True)
    except Exception as e:  # noqa: BLE001
        check("brief present and unchanged since freeze", False, str(e))

    dq = read_json("outputs/data_quality_report.json")
    check("detected duplicates equal injected", dq["duplicates"]["match"])
    check("out-of-order detected equals injected", dq["out_of_order"]["match"])
    check("legitimate retries kept equal ground truth",
          dq["legitimate_repeats_kept"]["total"] == read_json("outputs/ground_truth.json")["realised"][
              "legitimate_kyc_retries"])
    check("SRM passed on main data", read_json("outputs/srm.json")["passed"])
    v = read_json("outputs/validation_sims.json")
    for k in ("aa_test", "ci_coverage", "srm_detection", "peeking"):
        check(f"validation simulation {k} passed", v[k]["passed"])

    try:
        fresh = [c["text"] for c in render_all()]
        saved = [c["text"] for c in read_json("outputs/claims_rendered.json")["claims"]]
        check("claims re-render to saved text", fresh == saved, f"{len(fresh)} claims")
    except Exception as e:  # noqa: BLE001
        check("claims re-render to saved text", False, str(e))

    passed = sum(c["passed"] for c in checks)
    write_json("outputs/validation_report.json", {"simulated": True, "checks_total": len(checks),
                                                  "checks_passed": passed, "all_passed": passed == len(checks),
                                                  "checks": checks})
    for c in checks:
        print(("PASS " if c["passed"] else "FAIL ") + c["check"])
    print(f"{passed}/{len(checks)} checks passed")
    if passed != len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
