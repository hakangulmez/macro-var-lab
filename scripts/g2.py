"""Offline estimates; --pilot uses 20 resumable bootstrap replications per baseline."""

import argparse
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
from pathlib import Path

from macro_var_lab.g2 import run

parser = argparse.ArgumentParser()
parser.add_argument("--pilot", action="store_true")
args = parser.parse_args()
summary = run(Path.cwd(), Path("configs/g2.yaml"), pilot=args.pilot)
print({"kind": summary["kind"], "elapsed_seconds": summary["elapsed_seconds"], "paid_calls": 0})
