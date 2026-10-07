"""Acquire missing licensed inputs, then run G3 locally."""

import json
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
from pathlib import Path

from macro_var_lab.data import run as acquire
from macro_var_lab.release import run

root = Path.cwd()
checks = root / "results/g1_data_checks.json"
ready = checks.exists() and json.loads(checks.read_text()).get("status") == "data_checked"
if not ready or not (root / "data/processed/baseline_levels.csv").exists():
    result = acquire(root, root / "configs/data.yaml")
    if result["status"] != "data_checked":
        raise SystemExit("Source checks blocked; inspect results/g1_data_checks.json")
print({"gate": "G3", "seconds": run(root)["elapsed_seconds"], "paid_calls": 0})
