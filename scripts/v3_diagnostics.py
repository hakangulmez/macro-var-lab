# ruff: noqa: E501
"""Correct policy-only diagnostics; annotate inherited recursive accounting."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from macro_var_lab.g2 import prepare
from macro_var_lab.var import fit, history, residual_checks

root = Path(__file__).resolve().parents[1]
old = json.loads((root / "versions/v2-2026-10-07/results/g3_summary.json").read_text())
summary = json.loads(json.dumps(old))
frame = pd.read_csv(root / "data/processed/baseline_levels.csv", index_col=0)
frame.index = pd.PeriodIndex(frame.index, freq="M")
outputs = {}
histories = []
metadata = {}
checks = []
directory = root / "runs" / old["analysis_id"]
for name, record in old["models"].items():
    if "spec" not in record:
        continue
    spec = record["spec"]
    growth = spec["kind"] == "growth_robustness"
    y, d, labels, index = prepare(frame, spec, record["price_difference"], growth)
    if spec.get("easing_dummy"):
        d = np.column_stack(
            [d, ((index >= pd.Period("2021-09")) & (index <= pd.Period("2023-05"))).astype(float)]
        )
    if spec.get("fx_first"):
        y = y[:, [0, 1, 2, 3, 4, 6, 5]]
        labels = labels[:5] + ["fx", "policy"]
    model = fit(y, d, record["lag"], external=3 if spec["area"] == "TR" else 0)
    diag = residual_checks(model, labels)
    assert np.isclose(model.radius, record["radius"], rtol=1e-10)
    summary["models"][name]["diagnostics"]["granger_policy_to"] = diag["granger_policy_to"]
    summary["models"][name]["diagnostics"]["granger_tested_variable"] = diag[
        "granger_tested_variable"
    ]
    summary["models"][name]["diagnostics"]["granger_policy_column"] = diag["granger_policy_column"]
    outputs[name] = {
        key: diag[key]
        for key in ["granger_policy_to", "granger_tested_variable", "granger_policy_column"]
    }
    metadata[name] = dict(
        identification="recursive Cholesky",
        sample_start=str(index[model.start]),
        sample_end=str(index[-1]),
        lag=model.p,
    )
    if spec["kind"] == "baseline" and name.endswith("baseline"):
        # Reconstruct the exact inherited accounting and limit annual averages to
        # months represented by estimated residuals (pre-sample initializes dynamics).
        base, effects, error = history(model)
        price = labels.index("price")
        policy = labels.index("policy")
        difference = record["price_difference"]
        represented = y[:, price] if difference else np.diff(y[:, price], prepend=y[0, price])
        contributions = (
            effects[:, price, :]
            if difference
            else np.diff(effects[:, price, :], axis=0, prepend=np.zeros((1, len(labels))))
        )
        initial = base[:, price] if difference else np.diff(base[:, price], prepend=base[0, price])
        discrepancy = float(np.max(abs(initial + contributions.sum(axis=1) - represented)))
        assert discrepancy < 1e-7
        checks.append(
            dict(
                model=name,
                level_reconstruction_error=error,
                inflation_reconstruction_error=discrepancy,
                units="100 times monthly log price change; percentage points of monthly log inflation",
            )
        )
        with np.load(directory / name / "bootstrap.npz") as arrays:
            draws = arrays["history"]
        for year in sorted(set(index[model.start :].year)):
            mask = (index.year == year) & (np.arange(len(index)) >= model.start)
            selected = index[mask]
            means = draws[:, mask].mean(axis=1)
            lo, hi = np.quantile(means, [0.05, 0.95])
            histories.append(
                dict(
                    model=name,
                    year=int(year),
                    contributing_months=int(mask.sum()),
                    coverage_start=str(selected[0]),
                    coverage_end=str(selected[-1]),
                    partial_year=bool(mask.sum() < 12),
                    mean_inflation=float(represented[mask].mean()),
                    mean_policy_contribution=float(contributions[mask, policy].mean()),
                    lo90=float(lo),
                    hi90=float(hi),
                    aggregation="arithmetic year-average of monthly 100*delta(log P); not annual inflation; not annualised",
                    units="percentage points of monthly log inflation",
                    **metadata[name],
                )
            )
shares = pd.read_csv(root / "versions/v2-2026-10-07/results/g3_fevd.csv")
for key in ["identification", "sample_start", "sample_end", "lag"]:
    shares[key] = shares.model.map(lambda n: metadata[n][key])
shares["units"] = "fraction of forecast-error variance in native model outcome (not IRF-normalized)"
shares.to_csv(root / "results/g3_fevd.csv", index=False)
pd.DataFrame(histories).to_csv(root / "results/g3_history_annual.csv", index=False)
summary["v3_diagnostic_correction"] = dict(
    inherited_analysis_id=old["analysis_id"],
    only_granger_recomputed=True,
    HD_annual_means_reaggregated=True,
)
(root / "results/g3_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
(root / "results/v3_granger_diagnostics.json").write_text(json.dumps(outputs, indent=2) + "\n")
(root / "results/v3_hd_accounting.json").write_text(json.dumps(checks, indent=2) + "\n")
(root / "results/v3_accounting_manifest.json").write_text(
    json.dumps(
        dict(
            protocol_sha256=hashlib.sha256((root / "docs/V3_PROTOCOL.md").read_bytes()).hexdigest(),
            inherited_private_manifest_sha256=hashlib.sha256(
                (directory / "manifest.json").read_bytes()
            ).hexdigest(),
            HD_sample_convention="usable residual months only; prehistory omitted; 2026 partial; no annualisation",
            HD_scaling="inputs log variables already100log; level-price contributions differenced once; native TR inflation unchanged",
            FEVD_numeric_values="inherited unchanged",
            paid_calls=0,
        ),
        indent=2,
    )
    + "\n"
)
print(json.dumps(dict(models=len(outputs), HD_checks=checks)))
