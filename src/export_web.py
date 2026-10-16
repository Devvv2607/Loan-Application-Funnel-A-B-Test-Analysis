"""Phase 12: export verified outputs for the static website.

The site never computes a reported figure itself: it reads these JSON files.
Every file carries "simulated": true. Downloads are synthetic data, labelled so.
Refuses to run unless validate.py passed, so the site is only built from
outputs that agree with each other.
"""

from __future__ import annotations

import re
import shutil

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from common import ROOT, load_brief, read_json, settings, write_json

JSON_OUTPUTS = ["funnel_summary", "power_analysis", "feasibility", "srm", "experiment_results", "guardrails",
                "decision", "validation_sims", "claims_rendered", "validation_report", "data_manifest",
                "data_quality_report", "injected_issues", "ground_truth", "segment_summary", "brief_freeze"]
CSV_OUTPUTS = ["funnel_overall", "funnel_segments", "funnel_cube", "stage_timing", "segment_effects",
               "daily_cumulative", "mde_curve"]


def csv_rows(name: str) -> list[dict]:
    df = pd.read_csv(ROOT / "outputs" / f"{name}.csv", dtype={"segment": str, "city_tier": str})
    df = df.replace({np.nan: None})
    return df.to_dict(orient="records")


def simulation_parameters() -> list[dict]:
    """Parameter table with the one-line rationale from each line's comment in simulation.yaml."""
    text = (ROOT / "config" / "simulation.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    rows, stack, pending = [], [], None
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            pending = line.lstrip()[1:].strip() if stack else None  # a comment line rationalises the next key
            continue
        m = re.match(r"^(\s*)([^#\s][^:]*):\s*(.*?)\s*(?:#\s*(.*))?$", line)
        if not m:
            pending = None
            continue
        indent, key, value, comment = len(m.group(1)), m.group(2).strip().strip('"'), m.group(3), m.group(4)
        comment, pending = comment or pending, None
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        path = [k for _, k in stack]
        if comment:
            node = data
            for k in path:
                node = node[k] if k in node else node[str(k)] if str(k) in node else node[int(k)]
            shown = value if value else yaml.safe_dump(node, default_flow_style=True, sort_keys=False).strip()
            rows.append({"parameter": ".".join(path), "value": shown, "rationale": comment.strip()})
    return rows


def brief_for_web(brief: dict) -> dict:
    def clean(o):
        if isinstance(o, str):
            return " ".join(o.split())
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    return clean(brief)


def downloads(dest) -> dict:
    s = settings()
    raw = ROOT / s["paths"]["raw_dir"]
    users = pd.read_csv(raw / "users.csv", dtype={"city_tier": str})
    events = pd.read_csv(raw / "events.csv")
    loans = pd.read_csv(raw / "loans.csv")
    rng = np.random.default_rng(s["seed"])
    sample_ids = set(rng.choice(users["user_id"].to_numpy(), size=5000, replace=False))
    sample = events[events["user_id"].isin(sample_ids)].merge(
        users[["user_id", "device", "channel", "city_tier", "period", "variant"]], on="user_id", how="left")
    sample = sample.sort_values(["event_ts", "event_id"])
    sample.insert(0, "synthetic_data_notice", "SIMULATED - fictional lender")
    sample.to_csv(dest / "synthetic_event_log_sample_5000_users.csv", index=False, lineterminator="\n")
    files = {"sample_csv": "synthetic_event_log_sample_5000_users.csv"}

    full = dest / "synthetic_dataset_full.parquet"
    tables = {"users": users, "events": events, "loans": loans}
    # One parquet with a table column would mix schemas; write the event log joined to users,
    # which is the dataset the funnel is built from. Loans stay in the per-table CSV outputs.
    joined = events.merge(users, on="user_id", how="left")
    pq.write_table(pa.Table.from_pandas(joined, preserve_index=False), full, compression="zstd")
    size_mb = full.stat().st_size / 1e6
    if size_mb < 10:
        files["full_parquet"] = full.name
    else:
        full.unlink()
    files["full_parquet_size_mb"] = round(size_mb, 2)
    files["rows"] = {k: len(v) for k, v in tables.items()}
    for name in CSV_OUTPUTS:
        shutil.copy(ROOT / "outputs" / f"{name}.csv", dest / f"{name}.csv")
    shutil.copy(ROOT / "outputs" / "claims_rendered.json", dest / "claims_rendered.json")
    files["aggregated_csv"] = [f"{n}.csv" for n in CSV_OUTPUTS]
    return files


def main() -> None:
    if not read_json("outputs/validation_report.json")["all_passed"]:
        raise SystemExit("validate.py has failing checks; refusing to export the website data.")
    s = settings()
    out = ROOT / s["paths"]["web_data"]
    dl = ROOT / "web" / "public" / "downloads"
    for d in (out, dl):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    for name in JSON_OUTPUTS:
        write_json(out.relative_to(ROOT) / f"{name}.json", read_json(f"outputs/{name}.json"))
    for name in CSV_OUTPUTS:
        write_json(out.relative_to(ROOT) / f"{name}.json", {"simulated": True, "source": f"outputs/{name}.csv",
                                                            "rows": csv_rows(name)})
    brief = load_brief()
    write_json(out.relative_to(ROOT) / "experiment_brief.json", {"simulated": True,
                                                                  "source": "config/experiment_brief.yaml",
                                                                  "brief": brief_for_web(brief)})
    cfg = yaml.safe_load((ROOT / "config" / "simulation.yaml").read_text(encoding="utf-8"))
    write_json(out.relative_to(ROOT) / "simulation.json", {
        "simulated": True, "source": "config/simulation.yaml", "parameters": simulation_parameters(),
        "periods": s["periods"], "total_users": cfg["population"]["total_users"], "seed": s["seed"]})
    memo = (ROOT / s["paths"]["memo"]).read_text(encoding="utf-8")
    write_json(out.relative_to(ROOT) / "memo.json", {"simulated": True, "source": "memo/recommendation.md",
                                                     "markdown": memo})
    files = downloads(dl)
    write_json(out.relative_to(ROOT) / "site.json", {
        "simulated": True, **s["site"], "seed": s["seed"], "python_version": "3.11",
        "downloads": files,
        "pipeline": ["python make.py setup", "python make.py all", "python make.py test", "python make.py web"],
        "stages": ["simulate", "ingest", "clean", "funnel", "power", "experiment", "guardrails", "segments",
                   "validation-sims", "decision", "claims", "validate", "export-web"],
    })
    print(f"exported {len(list(out.glob('*.json')))} JSON files; downloads: {files}")


if __name__ == "__main__":
    main()
