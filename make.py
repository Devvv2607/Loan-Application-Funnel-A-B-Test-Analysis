"""Cross-platform stand-in for the Makefile: `python make.py <target> [<target> ...]`."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = str(ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))

SCRIPTS = {
    "feasibility": "feasibility.py", "simulate": "simulate.py", "ingest": "ingest.py", "clean": "clean.py",
    "funnel": "funnel.py", "power": "power.py", "experiment": "experiment.py", "guardrails": "guardrails.py",
    "segments": "segments.py", "validation-sims": "validation_sims.py", "decision": "decision.py",
    "claims": "claims.py", "validate": "validate.py", "export-web": "export_web.py", "readme": "readme.py",
}
ALL = ["simulate", "ingest", "clean", "funnel", "power", "experiment", "guardrails", "segments",
       "validation-sims", "decision", "claims", "validate", "export-web", "readme"]


def run(target: str) -> None:
    if target == "all":
        for t in ALL:
            run(t)
        return
    if target == "setup":
        cmds = [[sys.executable, "-m", "venv", ".venv"], [PY, "-m", "pip", "install", "-r", "requirements.txt"]]
        cwd = ROOT
    elif target == "test":
        cmds, cwd = [[PY, "-m", "pytest", "-q"]], ROOT
    elif target == "lint":
        cmds, cwd = [[PY, "-m", "ruff", "check", "src", "tests"]], ROOT
    elif target == "web":
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        cmds = [[npm, "ci"], [npm, "run", "lint"], [npm, "run", "typecheck"], [npm, "test"], [npm, "run", "build"]]
        cwd = ROOT / "web"
    else:
        cmds, cwd = [[PY, SCRIPTS[target]]], ROOT / "src"
    for cmd in cmds:
        print(f"[{target}] {' '.join(cmd)}", flush=True)
        subprocess.run(cmd, cwd=cwd, check=True, env={**os.environ, "PYTHONUTF8": "1"})


if __name__ == "__main__":
    for t in sys.argv[1:] or ["all"]:
        run(t)
