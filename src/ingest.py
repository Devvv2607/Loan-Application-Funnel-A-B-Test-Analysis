"""Phase 2a: load the raw CSVs into DuckDB untouched and write a data manifest.

Raw tables keep every injected issue; cleaning happens in SQL (clean.py) so each
fix is visible and testable. The manifest (row counts + file hashes) lets
validate.py prove that later stages read exactly these files.
"""

from __future__ import annotations

import hashlib

import duckdb

from common import ROOT, settings, write_json

TABLES = {"raw_users": "users.csv", "raw_events": "events.csv", "raw_loans": "loans.csv"}
TYPES = {
    "raw_users": {"user_id": "VARCHAR", "signup_ts": "TIMESTAMP", "device": "VARCHAR", "channel": "VARCHAR",
                  "city_tier": "VARCHAR", "period": "VARCHAR", "variant": "VARCHAR", "assigned_ts": "TIMESTAMP"},
    "raw_events": {"event_id": "VARCHAR", "user_id": "VARCHAR", "event_name": "VARCHAR", "event_ts": "TIMESTAMP",
                   "decision_outcome": "VARCHAR"},
    "raw_loans": {"loan_id": "VARCHAR", "user_id": "VARCHAR", "disbursed_ts": "TIMESTAMP", "amount": "DOUBLE",
                  "first_emi_due_ts": "TIMESTAMP", "dpd_30_on_first_emi": "INTEGER"},
}


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(ROOT / settings()["paths"]["duckdb"]), read_only=read_only)


def main() -> None:
    s = settings()
    raw = ROOT / s["paths"]["raw_dir"]
    db = ROOT / s["paths"]["duckdb"]
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    con = connect()
    files = {}
    for table, fname in TABLES.items():
        p = raw / fname
        cols = ", ".join(f"'{c}': '{t}'" for c, t in TYPES[table].items())
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv('{p.as_posix()}', header=true, "
                    f"columns={{{cols}}}, nullstr='')")
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        files[fname] = {"table": table, "rows": int(n), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    con.close()
    write_json("outputs/data_manifest.json", {"simulated": True, "seed": s["seed"], "raw_dir": s["paths"]["raw_dir"],
                                              "files": files})
    print({k: v["rows"] for k, v in files.items()})


if __name__ == "__main__":
    main()
