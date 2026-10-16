"""Generator tests: determinism, sizes, realised rates vs configured model, assignment."""

import hashlib
import math

import pandas as pd
import pytest

from common import read_json, settings, sim_config
from simulate import assign_variant, generate, write_raw


@pytest.fixture(scope="module")
def run42():
    return generate(42)


def _digest(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.csv"))}


def test_same_seed_byte_identical_and_different_seed_differs(tmp_path, run42):
    write_raw(run42, tmp_path / "a")
    write_raw(generate(42), tmp_path / "b")
    write_raw(generate(43), tmp_path / "c")
    a, b, c = _digest(tmp_path / "a"), _digest(tmp_path / "b"), _digest(tmp_path / "c")
    assert a == b
    assert a["events.csv"] != c["events.csv"]


def test_user_counts_and_period_sizes(run42):
    users = run42["users"]
    cfg, per = sim_config(), settings()["periods"]
    assert len(users) == cfg["population"]["total_users"]
    assert users["user_id"].is_unique
    # Whole weeks with identical day-of-week weights: expected pre share = pre_weeks / total_weeks.
    expected_pre = per["pre_period_weeks"] / (per["pre_period_weeks"] + per["experiment_weeks"])
    n = len(users)
    se = math.sqrt(expected_pre * (1 - expected_pre) / n)
    assert abs((users["period"] == "pre").mean() - expected_pre) < 4 * se


def test_realised_stage_conversions_match_model(run42):
    """Large-sample check: pre-period stage reach shares are within 4 SE of the model.

    Small slack covers the 60 injected missing-step users.
    """
    gt = read_json("outputs/ground_truth.json")["pre_period_funnel"]["reach_share_of_applicants"]
    users, ev = run42["users"], run42["events"]
    pre = set(users.loc[users["period"] == "pre", "user_id"])
    n = len(pre)
    e = ev[ev["user_id"].isin(pre) & ~ev["is_dup"]]
    observed = {
        "kyc_started": e.loc[e["event_name"] == "kyc_started", "user_id"].nunique() / n,
        "kyc_completed": e.loc[e["event_name"] == "kyc_completed", "user_id"].nunique() / n,
        "decision_made": e.loc[e["event_name"] == "decision_made", "user_id"].nunique() / n,
        "loan_disbursed": e.loc[e["event_name"] == "loan_disbursed", "user_id"].nunique() / n,
    }
    for stage, obs in observed.items():
        p = gt[stage]
        assert abs(obs - p) < 4 * math.sqrt(p * (1 - p) / n) + 0.002, (stage, obs, p)


def test_hash_assignment_reproducible_and_balanced(run42):
    users = run42["users"]
    rz = users[users["variant"].notna()]
    assert (rz["period"] == "experiment").all()
    assert all(assign_variant(42, u) == v for u, v in zip(rz["user_id"].head(500), rz["variant"].head(500)))
    share = (rz["variant"] == "treatment").mean()
    assert abs(share - 0.5) <= 0.005
    # Never-randomized users: pre-period, or never started KYC.
    assert users.loc[users["period"] == "pre", "variant"].isna().all()


def test_injected_counts_recorded(run42):
    inj = read_json("outputs/injected_issues.json")
    assert inj["duplicate_events"] == int(run42["events"]["is_dup"].sum())
    assert inj["out_of_order_events"] == int(run42["events"]["is_ooo"].sum() - run42["events"].loc[
        run42["events"]["is_dup"], "is_ooo"].sum())
    assert inj["null_device_users"] == int(run42["users"]["device"].isna().sum())
    assert inj["legitimate_kyc_retries_present"] == read_json("outputs/ground_truth.json")["realised"][
        "legitimate_kyc_retries"]


def test_raw_files_match_generator(run42):
    from common import ROOT
    raw = ROOT / settings()["paths"]["raw_dir"]
    assert len(pd.read_csv(raw / "users.csv")) == len(run42["users"])
    assert len(pd.read_csv(raw / "events.csv")) == len(run42["events"])


def test_every_simulation_parameter_has_a_rationale():
    """Hard rule: each parameter carries a one-line rationale (own comment or its block's)."""
    import yaml

    from common import ROOT
    from export_web import simulation_parameters

    covered = [r["parameter"] for r in simulation_parameters()]
    data = yaml.safe_load((ROOT / "config" / "simulation.yaml").read_text(encoding="utf-8"))

    def leaves(node, prefix):
        if isinstance(node, dict):
            for k, v in node.items():
                yield from leaves(v, f"{prefix}.{k}" if prefix else str(k))
        else:
            yield prefix

    for leaf in leaves(data, ""):
        assert any(leaf == c or leaf.startswith(c + ".") for c in covered), leaf
