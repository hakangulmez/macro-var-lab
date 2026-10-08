# ruff: noqa: E501
"""Predeclared controlled comparison; refuse unavailable pre-sample observations."""

import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl  # type: ignore[import-untyped]
import pandas as pd

from macro_var_lab.g2 import prepare, quantiles
from macro_var_lab.identification import hac_bands, rotations
from macro_var_lab.release import table_rows
from macro_var_lab.release_stats import cumulative_lp, kilian_draws, proxy_impact
from macro_var_lab.var import fit, ma, recursive


def required_panel(frame, start="2004-09", end="2025-10"):
    start = pd.Period(start, "M")
    end = pd.Period(end, "M")
    names = ["brent", "vix", "ea_ip", "ea_hicp", "ea_2y", "eurusd"]
    index = pd.period_range(start - 7, end, freq="M")
    panel = frame[names].reindex(index)
    missing = {
        key: [str(t) for t in panel.index[panel[key].isna()]]
        for key in names
        if panel[key].isna().any()
    }
    return panel, missing


def run(root: Path, start="2004-09"):
    began = time.monotonic()
    deadline = began + 7200
    frame = pd.read_csv(root / "data/processed/baseline_levels.csv", index_col=0)
    frame.index = pd.PeriodIndex(frame.index, freq="M")
    _, missing = required_panel(frame, start)
    manifest = dict(
        protocol_sha256=hashlib.sha256((root / "docs/V3_PROTOCOL.md").read_bytes()).hexdigest(),
        requested_usable_start=start,
        requested_usable_end="2025-10",
        lags=[3, 7],
        missing=missing,
        paid_calls=0,
        input_sha256=hashlib.sha256(
            (root / "data/processed/baseline_levels.csv").read_bytes()
        ).hexdigest(),
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    if missing:
        manifest.update(status="unsupported_missing_frozen_presample", new_estimation=False)
        (root / "results/v3_methods_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        pd.DataFrame(
            [
                dict(
                    lag=p,
                    status=manifest["status"],
                    usable_start=start,
                    usable_end="2025-10",
                    reason=json.dumps(missing),
                )
                for p in [3, 7]
            ]
        ).to_csv(root / "results/v3_methods_status.csv", index=False)
        print(json.dumps(manifest))
        return manifest
    spec = dict(
        area="EA",
        policy="ea_2y",
        price="ea_hicp",
        start=str(pd.Period(start, "M") - 7),
        end="2025-10",
    )
    y, d, labels, index = prepare(frame, spec, False)
    old = json.loads((root / "versions/v2-2026-10-07/results/g3_summary.json").read_text())
    workbook = root / "runs" / old["analysis_id"] / "EA-MPD.xlsx"
    if not workbook.exists():
        raise FileNotFoundError("Frozen EA-MPD workbook required; no acquisition")
    rows = list(
        openpyxl.load_workbook(workbook, read_only=True, data_only=True)[
            "Monetary Event Window"
        ].iter_rows(max_col=46, values_only=True)
    )
    column = list(rows[0]).index("OIS_2Y")
    events = []
    for row in rows[1:]:
        if row[0] is None or row[column] is None:
            continue
        date = (
            pd.to_datetime(row[0], format="%d/%m/%Y")
            if isinstance(row[0], str)
            else pd.Timestamp(row[0])
        )
        events.append((date.to_period("M"), float(row[column])))
    z = (
        pd.Series([v for _, v in events], index=[t for t, _ in events])
        .groupby(level=0)
        .sum()
        .reindex(pd.period_range("1999-01", "2025-10", freq="M"), fill_value=0)
    )
    manifest["instrument_workbook_sha256"] = hashlib.sha256(workbook.read_bytes()).hexdigest()
    manifest["panels"] = {}
    token = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    private = root / "runs" / ("v3_methods_" + token)
    private.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for p in [3, 7]:
        if time.monotonic() > deadline:
            raise TimeoutError("Comparison fixed2h budget")
        model = fit(y, d, p, start=7)
        policy = labels.index("policy")
        price = labels.index("price")
        point = recursive(model, policy, 36)[0]
        draws, km = kilian_draws(model, policy, 36, 20261007, 200, 499)
        np.savez_compressed(private / f"p{p}_recursive.npz", draws=draws)
        rows = table_rows(f"p{p}", labels, point, quantiles(draws), "recursive VAR")
        lp, se, counts = cumulative_lp(model, policy, 36, False)
        rows += table_rows(f"p{p}", labels, lp, hac_bands(lp, se), "recursive-shock LP")
        signs, sm = rotations(
            model, policy, price, 36, np.random.default_rng(20261007), 1000, 200000, 0.1, False
        )
        if len(signs):
            rows += table_rows(
                f"p{p}",
                labels,
                np.median(signs, axis=0),
                {"min": signs.min(axis=0), "max": signs.max(axis=0)},
                "sign-restricted VAR",
            )
        instrument = z.reindex(index[model.start :]).to_numpy()
        impact, info = proxy_impact(model, instrument, policy)
        accepted = []
        rejected = 0
        if np.isfinite(impact).all():
            proxy = ma(model, 36) @ impact
            rng = np.random.default_rng(20261007)
            for _ in range(499):
                starts = rng.integers(0, len(instrument), size=(len(instrument) + 5) // 6)
                ix = np.concatenate([(s + np.arange(6)) % len(instrument) for s in starts])[
                    : len(instrument)
                ]
                a, meta = proxy_impact(
                    replace(model, resid=model.resid[ix]), instrument[ix], policy
                )
                if np.isfinite(a).all():
                    accepted.append(ma(model, 36) @ a)
                else:
                    rejected += 1
            bands = quantiles(np.array(accepted)) if len(accepted) >= 100 else {}
            rows += table_rows(f"p{p}", labels, proxy, bands, "proxy VAR")
            if len(accepted) < 100:
                info["status"] = "insufficient_bootstrap"
        else:
            rows += table_rows(f"p{p}", labels, np.full_like(point, np.nan), {}, "proxy VAR")
        info.update(
            successful_draws=len(accepted),
            failed_strength_draws=rejected,
            total_draws=499 if np.isfinite(impact).all() else 0,
            inference="conditional on fixed VAR coefficients and strength-selected draws; not weak-IV robust",
            instrument="Monetary Event Window/OIS_2Y",
        )
        for row in rows:
            method = row["method"]
            row.update(
                lag=p,
                usable_start=str(index[7]),
                usable_end=str(index[-1]),
                usable_nobs=len(model.resid),
                shock_identification="recursive Cholesky"
                if method.startswith("recursive")
                else ("sign restrictions" if method.startswith("sign") else "external instrument"),
                response_estimator="local projection"
                if method.endswith("LP")
                else "VAR moving-average propagation",
                units=(
                    "pp response per100bp tightening"
                    if row["variable"] == "policy"
                    else "unscaled log response per100bp tightening"
                    if row["variable"] == "vix"
                    else "100 log response per100bp tightening"
                ),
                uncertainty="finite sign-admissible range"
                if method.startswith("sign")
                else (
                    "pointwise conditional90/68 intervals"
                    if method == "proxy VAR"
                    else "pointwise90/68 intervals"
                ),
                status=info["status"] if method == "proxy VAR" else "estimated",
                LP_count=int(counts[row["horizon"]]) if method.endswith("LP") else np.nan,
            )
        all_rows += rows
        manifest["panels"][str(p)] = dict(
            radius=model.radius,
            proxy=info,
            signs=sm,
            kilian=km,
            LP_counts=counts.tolist(),
            usable_sample=[str(index[7]), str(index[-1])],
            nobs=len(model.resid),
        )
        pd.DataFrame(all_rows).to_csv(private / "checkpoint.csv", index=False)
    table = pd.DataFrame(all_rows)
    table.to_csv(root / "results/v3_methods_irfs.csv", index=False)
    table[(table.horizon == 12) & table.variable.isin(["price", "activity", "fx"])].to_csv(
        root / "results/v3_methods_comparison.csv", index=False
    )
    manifest.update(
        status="completed",
        elapsed_seconds=time.monotonic() - began,
        analysis_id=private.name,
        new_estimation=True,
    )
    (root / "results/v3_methods_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (private / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), sharex=True)
    palette = ["#0072B2", "#009E73", "#E69F00", "#D55E00"]
    for i, p in enumerate([3, 7]):
        for j, variable in enumerate(["price", "activity", "fx"]):
            ax = axes[i, j]
            for method, color in zip(
                ["recursive VAR", "recursive-shock LP", "sign-restricted VAR", "proxy VAR"],
                palette,
                strict=True,
            ):
                part = table[
                    (table.lag == p) & (table.variable == variable) & (table.method == method)
                ].sort_values("horizon")
                ax.plot(part.horizon, part.estimate, label=method, color=color, lw=1.3)
                if method.startswith("sign"):
                    if "min" in part:
                        ax.plot(part.horizon, part["min"], ls="--", lw=0.6, color=color)
                        ax.plot(part.horizon, part["max"], ls="--", lw=0.6, color=color)
                elif "lo90" in part:
                    ax.fill_between(part.horizon, part.lo90, part.hi90, color=color, alpha=0.15)
            ax.axhline(0, color=".4", lw=0.5)
            ax.set(title=f"p={p}: {variable}", xlabel="Months", ylabel="100 log response")
            limits = table[
                (table.lag == p)
                & (table.variable == variable)
                & (~table.method.str.startswith("sign"))
            ][["lo90", "hi90"]].to_numpy()
            lo, hi = np.nanmin(limits), np.nanmax(limits)
            pad = 0.1 * (hi - lo)
            ax.set_ylim(lo - pad, hi + pad)
    handles, labels_ = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels_, loc="lower center", ncol=4, fontsize=9)
    fig.suptitle(
        "Methods comparison on a common sample and lag specification\n"
        + start
        + "–2025-10; identical usable VAR dates within both panels"
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.93))
    fig.savefig(root / "figures/v3_methods_comparison.png", dpi=250)
    plt.close(fig)
    print(json.dumps(manifest), flush=True)
    return manifest
