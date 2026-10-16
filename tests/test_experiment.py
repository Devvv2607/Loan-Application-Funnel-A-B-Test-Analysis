"""Experiment tests: SRM, statsmodels parity, intention-to-treat denominators, brief gate."""

import shutil

import numpy as np
import pytest
from scipy.stats import chisquare
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest

import common
from abstats import newcombe_diff_ci, ratio_ci_log, srm_chisquare, ztest_two_proportions
from common import read_json


def test_srm_matches_scipy():
    srm = read_json("outputs/srm.json")
    obs = [srm["observed"]["control"], srm["observed"]["treatment"]]
    ref = chisquare(obs)
    assert abs(srm["chi2"] - ref.statistic) < 1e-9
    assert abs(srm["p_value"] - ref.pvalue) < 1e-9
    assert srm["passed"]


@pytest.mark.parametrize("xc,nc,xt,nt", [(4323, 8639, 4771, 8740), (50, 400, 70, 410), (900, 1000, 880, 1000),
                                         (134, 8639, 148, 8740)])
def test_ztest_and_cis_match_statsmodels(xc, nc, xt, nt):
    z, p = ztest_two_proportions(xc, nc, xt, nt)
    sz, sp = proportions_ztest([xt, xc], [nt, nc])
    assert abs(z - sz) < 1e-9 and abs(p - sp) < 1e-9
    lo, hi = newcombe_diff_ci(xc, nc, xt, nt)
    slo, shi = confint_proportions_2indep(xt, nt, xc, nc, method="newcomb", compare="diff")
    assert abs(lo - slo) < 1e-9 and abs(hi - shi) < 1e-9
    _, rlo, rhi = ratio_ci_log(xc, nc, xt, nt)
    srlo, srhi = confint_proportions_2indep(xt, nt, xc, nc, method="log", compare="ratio")
    assert abs(rlo - srlo) < 1e-9 and abs(rhi - srhi) < 1e-9


def test_reported_results_match_statsmodels():
    r = read_json("outputs/experiment_results.json")
    for key in ("primary", "secondary"):
        m = r[key]
        cc = m["cross_check_statsmodels"]
        assert abs(m["z"] - cc["z"]) < 1e-9
        assert abs(m["p_value"] - cc["p_value"]) < 1e-9 * max(1, m["p_value"]) + 1e-15
        np.testing.assert_allclose(m["diff_ci_pp"], cc["diff_ci_pp"], atol=1e-7)


def test_srm_function_matches_scipy_on_unbalanced_split():
    stat, p = srm_chisquare([5200, 4800], [0.5, 0.5])
    ref = chisquare([5200, 4800])
    assert abs(stat - ref.statistic) < 1e-9 and abs(p - ref.pvalue) < 1e-12


def test_intention_to_treat_denominators_identical_everywhere():
    r = read_json("outputs/experiment_results.json")
    counts = r["assignment_counts"]
    assert read_json("outputs/srm.json")["observed"] == counts
    assert read_json("outputs/guardrails.json")["assignment_counts"] == counts
    assert read_json("outputs/power_analysis.json")["experiment_assignment_counts"] == counts
    for arm in ("control", "treatment"):
        assert r["primary"][arm]["denominator"] == counts[arm]
        assert r["secondary"][arm]["denominator"] == counts[arm]
        assert r["arm_counts"][arm]["randomized"] == counts[arm]


def test_no_post_randomization_denominator_except_labelled_diagnostics():
    counts = read_json("outputs/experiment_results.json")["assignment_counts"]
    for name, g in read_json("outputs/guardrails.json")["guardrails"].items():
        itt = all(g[arm]["denominator"] == counts[arm] for arm in ("control", "treatment"))
        if g["role"] == "decision":
            assert itt, name
        else:
            assert not itt and g["role"] == "diagnostic", name


def test_assignment_counts_match_raw_assignment_log():
    import pandas as pd
    users = pd.read_csv(common.ROOT / "data" / "raw" / "users.csv")
    raw = users["variant"].value_counts().to_dict()
    assert raw == read_json("outputs/experiment_results.json")["assignment_counts"]


def test_analysis_refuses_without_brief(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(common, "ROOT", tmp_path)
    import experiment
    with pytest.raises(common.BriefMissingError):
        experiment.main()
    (tmp_path / "config" / "experiment_brief.yaml").write_text("# empty\n", encoding="utf-8")
    with pytest.raises(common.BriefMissingError):
        common.load_brief()


def test_edited_brief_is_rejected(tmp_path, monkeypatch):
    real = common.ROOT
    (tmp_path / "config").mkdir()
    (tmp_path / "outputs").mkdir()
    shutil.copy(real / "outputs" / "brief_freeze.json", tmp_path / "outputs")
    text = (real / "config" / "experiment_brief.yaml").read_text(encoding="utf-8")
    (tmp_path / "config" / "experiment_brief.yaml").write_text(text.replace("margin: 2.1", "margin: 9.9"),
                                                               encoding="utf-8")
    monkeypatch.setattr(common, "ROOT", tmp_path)
    with pytest.raises(common.BriefMissingError):
        common.load_brief()
