"""Read-only final G3 evidence, integrity and publication-boundary audit."""

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from macro_var_lab.access import read_keys

root = Path.cwd()
s = json.loads((root / "results/g3_summary.json").read_text())
checks = []


def check(name, ok, detail):
    checks.append({"check": name, "passed": bool(ok), "detail": detail})


reproduction = json.loads((root / "results/reproduction_check.json").read_text())
contract = s["contract"]
check(
    "input hash",
    hashlib.sha256((root / "data/processed/baseline_levels.csv").read_bytes()).hexdigest()
    == contract["input_sha256"],
    "Approved G1 panel",
)
for name, digest in contract["code"].items():
    current = hashlib.sha256((root / name).read_bytes()).hexdigest()
    transition = reproduction.get("code_transitions", {}).get(name)
    if transition is None or current == digest:
        check("estimator code hash", current == digest, name)
    else:
        historical = (root / transition["public_source_snapshot"]).read_bytes()
        check(
            "authorized acquisition-only transition",
            hashlib.sha256(historical).hexdigest() == digest == transition["original_sha256"]
            and current == transition["reproduced_sha256"],
            name,
        )
for name, m in s["models"].items():
    if "plain_bootstrap" in m:
        check("bootstrap completion", m["plain_bootstrap"]["status"] == "complete", name)
    if "history_reconstruction_error" in m:
        check("historical accounting", m["history_reconstruction_error"] < 1e-5, name)
irf = pd.read_csv(root / "results/g3_irfs.csv")
for area in ["EA", "TR"]:
    part = irf[
        (irf.model == area + "_baseline")
        & (irf.variable == "policy")
        & (irf.horizon == 0)
        & (irf.method == "recursive")
    ]
    check("100 bp impact", np.allclose(part.estimate, 1), area)
check("paid calls", s["paid_calls"] == 0, "No paid APIs")
check(
    "proxy coverage",
    s["proxy"].get("sample", [None, None])[-1] == "2025-10",
    "Later months missing",
)
check("proxy relevance gate", s["proxy"].get("F", 0) > 10, "Conditional exclusion not tested")
tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
keys = list(read_keys(root / ".env").values())
leaks = 0
for name in filter(None, tracked):
    path = root / name
    if path.is_file():
        b = path.read_bytes()
        leaks += sum(key.encode() in b for key in keys)
check("tracked credential scan", leaks == 0, "Exact local credential values never printed")
check(
    "private inputs ignored",
    not any(
        x.startswith(("data/raw/", "data/processed/", "runs/", ".venv/")) or x == ".env"
        for x in tracked
    ),
    "No third-party raw data in Git",
)
check(
    "authorized publication origin",
    all(
        url
        in {
            "https://github.com/hakangulmez/macro-var-lab",
            "https://github.com/hakangulmez/macro-var-lab.git",
        }
        for url in subprocess.check_output(
            ["git", "remote", "get-url", "--all", "origin"], cwd=root, stderr=subprocess.DEVNULL
        )
        .decode()
        .splitlines()
    )
    if subprocess.check_output(["git", "remote"], cwd=root).strip()
    else True,
    "Only the owner-approved public repository is allowed",
)
result = {
    "checks": checks,
    "all_integrity_checks_pass": all(x["passed"] for x in checks),
    "fresh_clone_acceptance": json.loads((root / "results/reproduction_check.json").read_text())[
        "status"
    ],
    "policy_pdf_visual_qa": "two pages inspected",
}
(root / "results/release_audit.json").write_text(json.dumps(result, indent=2) + "\n")
print(
    json.dumps(
        {
            "checks": len(checks),
            "integrity_pass": result["all_integrity_checks_pass"],
            "fresh_clone": result["fresh_clone_acceptance"],
        }
    )
)
