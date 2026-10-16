"""Claims and conventions: rendered numbers equal source metrics; terminology; simulated flag."""

import json

import pytest
import yaml

from claims import ClaimError, render_all, resolve
from common import ROOT, read_json


def test_every_rendered_claim_matches_its_source_metrics():
    rendered = {c["id"]: c for c in read_json("outputs/claims_rendered.json")["claims"]}
    reg = yaml.safe_load((ROOT / "outputs" / "claims.yaml").read_text(encoding="utf-8"))
    assert set(rendered) == {c["id"] for c in reg["claims"]}
    for c in reg["claims"]:
        values = {k: resolve(ref) for k, ref in c["metrics"].items()}
        r = rendered[c["id"]]
        assert {k: v["value"] for k, v in r["metrics"].items()} == values
        assert r["text"] == c["template"].format(**values)


def test_fresh_render_equals_saved():
    saved = read_json("outputs/claims_rendered.json")["claims"]
    assert [c["text"] for c in render_all()] == [c["text"] for c in saved]


def test_missing_metric_fails():
    with pytest.raises(ClaimError):
        resolve("experiment_results.json:primary.no_such_metric")


def test_claim_ids_use_registered_prefixes():
    for c in read_json("outputs/claims_rendered.json")["claims"]:
        assert c["id"].split("-")[0] in {"FUN", "PWR", "EXP", "GRD", "VAL", "DEC"}


def _user_facing_files():
    files = [ROOT / "memo" / "recommendation.md", ROOT / "outputs" / "resume_bullets.md"]
    files += sorted((ROOT / "outputs").glob("*.json"))
    web = ROOT / "web" / "public" / "data"
    if web.exists():
        files += sorted(web.glob("*.json"))
    return files


def test_no_default_rate_wording():
    for f in _user_facing_files():
        assert "default rate" not in f.read_text(encoding="utf-8").lower(), f.name


def test_every_json_output_is_flagged_simulated():
    for f in _user_facing_files():
        if f.suffix == ".json":
            assert json.loads(f.read_text(encoding="utf-8")).get("simulated") is True, f.name


def test_resume_bullets_say_simulated():
    text = (ROOT / "outputs" / "resume_bullets.md").read_text(encoding="utf-8").lower()
    assert "simulated" in text
