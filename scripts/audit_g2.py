"""Read-only G2 audit; writes aggregate checks, never rewrites estimates or inputs."""

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from macro_var_lab.access import read_keys

root = Path.cwd()
summary = json.loads((root / "results/g2_summary.json").read_text())
run = root / "runs" / summary["analysis_id"]
manifest = json.loads((run / "manifest.json").read_text())
g1 = json.loads((root / "runs" / summary["G1_run"] / "manifest.json").read_text())
checks = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name, passed, detail):
    checks.append(dict(check=name, passed=bool(passed), detail=detail))


check("G1 identity", summary["G1_run"] == manifest["source_manifest"], summary["G1_run"])
for path, expected in g1["processed_sha256"].items():
    check("unchanged approved G1 observation file", sha(root / path) == expected, path)
for label, record in g1["sources"].items():
    raw = (
        root / "data/raw/responses" / (hashlib.sha256(record["url"].encode()).hexdigest() + ".bin")
    )
    check("unchanged original source payload", sha(raw) == record["sha256"], label)
check(
    "G2 input bound to G1",
    summary["contract"]["input_sha256"]
    == g1["processed_sha256"]["data/processed/baseline_levels.csv"],
    "baseline_levels.csv",
)
check(
    "summary manifest checksum",
    sha(root / "results/g2_summary.json") == manifest["summary_sha256"],
    "Final estimator summary; artifact generator has separate provenance",
)
for path, expected in summary["contract"]["code"].items():
    check("estimator code hash", sha(root / path) == expected, path)
config = yaml.safe_load((root / "configs/g2.yaml").read_text())
check("configuration", manifest["config_actual"] == config, "No undisclosed post-run spec changes")
check(
    "zero network and paid calls",
    manifest["network_calls"] == manifest["paid_calls"] == 0,
    "G2 estimator reads local CSV only; keys used here solely for credential-leak inspection",
)
irf = pd.read_csv(root / "results/g2_irfs.csv")
shares = pd.read_csv(root / "results/g2_fevd.csv")
for name, record in summary["models"].items():
    model_rows = irf[irf.model == name]
    check("horizon 0-36 contract", set(model_rows.horizon) == set(range(37)), name)
    check(
        "100 bp impact",
        np.allclose(
            model_rows[
                (model_rows.variable == "policy") & (model_rows.horizon == 0)
            ].estimate.dropna(),
            1,
            atol=1e-9,
        ),
        name,
    )
    if record.get("no_VAR_estimated"):
        check(
            "recent regime LP only",
            record["variables"] == ["activity", "price", "policy", "fx"]
            and record["months"] == 38
            and len(model_rows.method.unique()) == 1
            and not (run / name / "point.npz").exists(),
            name,
        )
        counts = record["LP_nobs_by_horizon"]
        check(
            "unavailable recent horizons preserved",
            all(
                model_rows.query("horizon == @h").estimate.isna().all()
                for h, n in enumerate(counts)
                if not n
            ),
            name,
        )
        continue
    check(
        "bootstrap complete",
        record["bootstrap"]["successful"] == 499 and record["bootstrap"]["status"] == "complete",
        name,
    )
    check(
        "sign draw complete",
        record["sign_restrictions"]["accepted"] == 1000
        and record["sign_restrictions"]["status"] == "complete",
        name,
    )
    signs = model_rows[(model_rows.method == "sign_rotation_set") & (model_rows.horizon <= 3)]
    check(
        "restricted sign medians",
        (signs[signs.variable == "price"].estimate <= 1e-9).all()
        and (signs[signs.variable == "policy"].estimate >= -1e-9).all(),
        name,
    )
    check(
        "stability flag truthful",
        record["residual_diagnostics"]["stable"]
        == (record["residual_diagnostics"]["companion_spectral_radius"] < 1),
        name,
    )
    check(
        "historical accounting",
        record["HD_level_reconstruction_error"] < 1e-5
        and record["HD_inflation_reconstruction_error"] < 1e-5,
        name,
    )
    total = shares[shares.model == name].groupby(["horizon", "variable"])["share"].sum()
    check("FEVD adds to one", np.allclose(total, 1, atol=1e-10), name)
    with np.load(run / name / "point.npz") as point:
        eps = point["innovations"]
        check(
            "orthogonal recursive innovations",
            np.allclose(eps.T @ eps / len(eps), np.eye(eps.shape[1]), atol=1e-9),
            name,
        )
        if name.startswith("TR"):
            check("external equation lag exclusions", np.all(point["coefs"][:, :3, 3:] == 0), name)
            check("external impact exclusion", np.all(point["impact"][:3, -2] == 0), name)
    with np.load(run / name / "bootstrap.npz") as draws:
        check(
            "bootstrap cache length",
            len(draws["var"]) == len(draws["lp"]) == len(draws["fevd"]) == 499,
            name,
        )
        if name.endswith("baseline"):
            check("HD uncertainty draw length", len(draws["history"]) == 499, name)
    history = pd.read_csv(run / name / "inflation_history_private.csv", index_col=0)
    check(
        "private HD row accounting",
        np.allclose(
            history[record["variables"]].sum(axis=1) + history.initial_deterministic,
            history.reconstruction,
            atol=1e-8,
        ),
        name,
    )
check(
    "TR approved switch recorded",
    summary["TR_transform_decision"]["trigger"] == "levels instability"
    and summary["TR_transform_decision"]["switch_to_inflation"],
    "No further tuning to force stability",
)
check(
    "VECM gate respected",
    summary["vecm"]["status"] == "not_estimated" and summary["vecm"]["no_Johansen_run"],
    "Mixed I(1) evidence; no rank or pass-through claim",
)
artifacts = json.loads((root / "results/g2_artifacts.json").read_text())
check(
    "artifact generator hash",
    sha(root / "scripts/g2_outputs.py") == artifacts["generator_sha256"],
    "All figures and review summary generated from recorded estimates",
)
for path, expected in artifacts["artifacts"].items():
    check("figure hash", sha(root / path) == expected, path)
keys = read_keys(root / ".env")
eligible = subprocess.check_output(
    ["git", "ls-files", "-co", "--exclude-standard"], text=True
).splitlines()
paths = (
    {root / p for p in eligible} | set((root / "data").rglob("*")) | set((root / "runs").rglob("*"))
)
leaks = [
    str(p.relative_to(root))
    for p in paths
    if p.is_file() and any(value.encode() in p.read_bytes() for value in keys.values())
]
check(
    "credential byte safety",
    not leaks,
    {
        "files_checked": sum(p.is_file() for p in paths),
        "key_presence": {name: True for name in keys},
        "leaking_paths": leaks,
    },
)
check(
    "no remote",
    not subprocess.check_output(["git", "remote"], text=True).strip(),
    "Local commits only",
)
check(
    "no private eligible paths",
    not any(
        p == ".env" or p.startswith(("data/raw/", "data/processed/", "runs/", ".venv/"))
        for p in eligible
    ),
    "Raw observations, HD checks, innovations and environments excluded",
)
result = dict(
    gate="G2",
    analysis_id=summary["analysis_id"],
    read_only_inputs=True,
    network_calls=0,
    passed=sum(c["passed"] for c in checks),
    failed=sum(not c["passed"] for c in checks),
    checks=checks,
    limitations=[
        "Code tests compare OLS/MA/LP-HAC to statsmodels and analytic identities.",
        "Audit checks numerical identities/sign medians, not economic identification truth.",
        "Unstable models and residual diagnostics limit nominal bootstrap coverage.",
        "Source/licence vintage remains G1; observations are not redistributed.",
        "Recent-regime shocks are retrospective full-sample shocks; no short-regime VAR.",
    ],
)
(root / "results/g2_audit.json").write_text(json.dumps(result, indent=2) + "\n")
print({k: result[k] for k in ["analysis_id", "passed", "failed", "network_calls"]})
if result["failed"]:
    print([c for c in checks if not c["passed"]])
    raise SystemExit(1)
