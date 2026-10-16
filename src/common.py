"""Shared helpers: project paths, config loading, deterministic JSON writing."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(name: str) -> dict:
    with open(ROOT / "config" / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def settings() -> dict:
    return load_yaml("settings.yaml")


def sim_config() -> dict:
    return load_yaml("simulation.yaml")


def path(key: str) -> Path:
    return ROOT / settings()["paths"][key]


def _round(obj, sig: int = 12):
    """Round floats so outputs are byte-stable across platforms; convert numpy scalars."""
    import numpy as np

    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        obj = float(obj)
    if isinstance(obj, float):
        return float(f"{obj:.{sig}g}")  # significant digits, so tiny p-values keep their precision
    if isinstance(obj, dict):
        return {k: _round(v, sig) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round(v, sig) for v in obj]
    return obj


def write_json(rel_path: str | Path, data: dict) -> Path:
    p = ROOT / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(_round(data), f, indent=2, sort_keys=False)
        f.write("\n")
    return p


def read_json(rel_path: str | Path) -> dict:
    with open(ROOT / rel_path, encoding="utf-8") as f:
        return json.load(f)


class BriefMissingError(RuntimeError):
    """Raised when the pre-registration is absent, empty or has been modified."""


def load_brief() -> dict:
    """Load the frozen pre-registration, refusing to proceed without it.

    Why: the decision rule must be fixed before results are seen. Analysis code
    reads the rule from this file, and a changed hash means it was edited after
    freezing, so the analysis stops rather than run under a moved goalpost.
    """
    import hashlib

    p = ROOT / "config" / "experiment_brief.yaml"
    if not p.exists():
        raise BriefMissingError("config/experiment_brief.yaml not found: pre-register before analysing.")
    brief = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "decision_rule" not in brief:
        raise BriefMissingError("experiment_brief.yaml has no decision_rule: pre-register before analysing.")
    freeze = ROOT / "outputs" / "brief_freeze.json"
    if freeze.exists():
        expected = json.loads(freeze.read_text(encoding="utf-8"))["sha256"]
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise BriefMissingError("experiment_brief.yaml changed after it was frozen.")
    return brief
