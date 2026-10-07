"""G3 orchestration; immutable caches and explicit changes from the G2 checkpoint."""

import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from macro_var_lab.access import Client
from macro_var_lab.g2 import bootstrap, prepare, quantiles, recent_lp, unit_root_gate
from macro_var_lab.identification import displayed, hac_bands, rotations
from macro_var_lab.release_stats import choose_lag, cumulative_lp, kilian_draws, proxy_impact
from macro_var_lab.var import fevd, history, ma, recursive, residual_checks


def table_rows(name, labels, point, bands, method):
    return [
        {
            "model": name,
            "method": method,
            "horizon": h,
            "variable": label,
            "estimate": float(point[h, j]),
            **{key: float(value[h, j]) for key, value in bands.items()},
        }
        for h in range(len(point))
        for j, label in enumerate(labels)
    ]


def run(root: Path, quick=False):
    began = time.monotonic()
    c = yaml.safe_load((root / "configs/g2.yaml").read_text())
    c.update(bias_draws=200, bootstrap_draws=499)
    if quick:
        c.update(bias_draws=3, bootstrap_draws=5, sign_draws=10, horizon=6)
    input_path = root / "data/processed/baseline_levels.csv"
    frame = pd.read_csv(input_path, index_col=0)
    frame.index = pd.PeriodIndex(frame.index, freq="M")
    contract = {
        "config": c,
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "code": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (root / "src").rglob("*.py")
        },
    }
    token = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()[:16]
    directory = root / "runs" / ("g3_" + token)
    directory.mkdir(parents=True, exist_ok=True)
    gates = unit_root_gate(frame)
    tr_spec = c["models"][1]
    y, d, labels, _ = prepare(frame, tr_spec, False)
    levels, _, checks = choose_lag(y, d, external=3)
    difference = bool(levels.radius >= 1 or gates["tr_cpi"]["I2_compatible_by_agreement_rule"])
    specs = c["models"][:2] if quick else c["models"]
    specs = specs + [
        dict(c["models"][0], name="EA_BIC", force_bic=True),
        dict(tr_spec, name="TR_BIC", force_bic=True),
        dict(tr_spec, name="TR_FX_first", fx_first=True),
        dict(tr_spec, name="TR_easing_dummy", easing_dummy=True),
    ]
    records, irfs, shares, hds = {}, [], [], []
    for n, spec in enumerate(specs):
        name = spec["name"]
        diff = (
            difference and spec["area"] == "TR" and spec["kind"] != "levels_comparison"
        ) or spec["kind"] == "growth_robustness"
        growth = spec["kind"] == "growth_robustness"
        y, d, labels, index = prepare(frame, spec, diff, growth)
        if spec.get("easing_dummy"):
            d = np.column_stack(
                [
                    d,
                    ((index >= pd.Period("2021-09")) & (index <= pd.Period("2023-05"))).astype(
                        float
                    ),
                ]
            )
        if spec.get("fx_first"):
            y = y[:, [0, 1, 2, 3, 4, 6, 5]]
            labels = labels[:5] + ["fx", "policy"]
        model, ic, lag_checks = choose_lag(
            y, d, external=3 if spec["area"] == "TR" else 0, force_bic=spec.get("force_bic", False)
        )
        policy, price = labels.index("policy"), labels.index("price")
        seed = int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big")
        native, _, _ = recursive(model, policy, c["horizon"])
        point = displayed(native, labels, diff, growth)
        cache = directory / name / "bootstrap.npz"
        arrays, plain_meta = bootstrap(
            model, labels, policy, c, cache, seed, diff, growth, spec["kind"] == "baseline"
        )
        irfs += table_rows(name, labels, point, quantiles(arrays["var"]), "plain_block")
        kcache = directory / name / "kilian.npz"
        if kcache.exists():
            with np.load(kcache) as a:
                kd = a["draws"]
            km = json.loads(kcache.with_suffix(".json").read_text())
        else:
            kd, km = kilian_draws(
                model, policy, c["horizon"], seed, c["bias_draws"], c["bootstrap_draws"]
            )
            kd = np.array([displayed(x, labels, diff, growth) for x in kd])
            np.savez_compressed(kcache, draws=kd)
            kcache.with_suffix(".json").write_text(json.dumps(km, indent=2))
        irfs += table_rows(name, labels, point, quantiles(kd), "recursive")
        # Cumulative dependent price outcome yields proper direct HAC level bands.
        # Ordering robustness uses native LP bootstrap inherited from G2 instead.
        if not spec.get("fx_first"):
            lp, se, counts = cumulative_lp(model, policy, c["horizon"], diff)
            irfs += table_rows(name, labels, lp, hac_bands(lp, se), "LP_HAC")
        else:
            lp, counts = point.copy() * np.nan, np.zeros(c["horizon"] + 1)
        signs, sign_meta = rotations(
            model,
            policy,
            price,
            c["horizon"],
            np.random.default_rng(seed),
            c["sign_draws"],
            c["sign_max_attempts"],
            0.1,
            diff,
        )
        if len(signs):
            signs = np.array([displayed(x, labels, diff, growth) for x in signs])
            irfs += table_rows(
                name,
                labels,
                np.median(signs, axis=0),
                {"min": signs.min(axis=0), "max": signs.max(axis=0)},
                "sign_set",
            )
        share = fevd(model, 36)
        sb = quantiles(arrays["fevd"])
        for h in range(min(c["horizon"], 36)):
            for j, label in enumerate(labels):
                shares.append(
                    {
                        "model": name,
                        "variable": label,
                        "horizon": h + 1,
                        "policy_share": share[h, j, policy],
                        **{key: value[h, j, policy] for key, value in sb.items()},
                    }
                )
        base, effects, error = history(model)
        actual = y[:, price] if diff else np.diff(y[:, price], prepend=y[0, price])
        contribution = effects[:, price, policy]
        contribution = contribution if diff else np.diff(contribution, prepend=0)
        history_table = pd.DataFrame(
            {"inflation": actual, "policy_contribution": contribution}, index=index
        )
        history_table.to_csv(directory / name / "history_private.csv")
        if spec["kind"] == "baseline" and name.endswith("baseline"):
            for period in range(2011 if spec["area"] == "TR" else 2004, 2027):
                selected = history_table[index.year == period]
                if len(selected):
                    hds.append(
                        {
                            "model": name,
                            "year": period,
                            "mean_inflation": selected.inflation.mean(),
                            "mean_policy_contribution": selected.policy_contribution.mean(),
                            **{
                                key: float(value)
                                for key, value in quantiles(
                                    arrays["history"][:, index.year == period].mean(axis=1)
                                ).items()
                            },
                        }
                    )
        records[name] = {
            "spec": spec,
            "lag": model.p,
            "lag_IC": ic,
            "LM_search": lag_checks,
            "LM_pass": bool(
                lag_checks[-1].get("pvalue") is not None and lag_checks[-1]["pvalue"] >= 0.05
            ),
            "price_difference": diff,
            "variables": labels,
            "radius": model.radius,
            "kilian": km,
            "plain_bootstrap": plain_meta,
            "diagnostics": residual_checks(model, labels),
            "history_reconstruction_error": error,
            "signs": sign_meta,
            "LP_observations": counts.tolist(),
        }
        if name == "TR_baseline" and not quick:
            offset = int(np.flatnonzero(index == pd.Period("2023-06"))[0])
            recent, se, counts = recent_lp(model, offset, c)
            # Native inflation HAC only; cumulative bands cannot be obtained by summing SEs.
            irfs += table_rows(
                "TR_recent_LP_native", labels[3:], recent, hac_bands(recent, se), "LP_HAC"
            )
            records["TR_recent_LP_native"] = {
                "no_VAR_estimated": True,
                "variables": labels[3:],
                "native_inflation_only": True,
                "horizons_unavailable": int(np.sum(counts == 0)),
            }
        print(
            json.dumps(
                {
                    "model": name,
                    "lag": model.p,
                    "LM_pass": records[name]["LM_pass"],
                    "radius": model.radius,
                }
            ),
            flush=True,
        )
    # Pass-through: recursive FX innovation, cumulative CPI, exact 10% depreciation.
    y, d, labels, _ = prepare(frame, tr_spec, difference)
    tr, _, _ = choose_lag(y, d, external=3)
    pt, ps, counts = cumulative_lp(tr, 5, 24, difference, shock_column=6, scale=100 * np.log(1.1))
    irfs += table_rows("TR_pass_through", labels, pt, hac_bands(pt, ps), "LP_HAC")
    proxy = {"status": "skipped_quick"} if quick else proxy_run(root, frame, c, irfs, directory)
    summary = {
        "contract": contract,
        "analysis_id": directory.name,
        "models": records,
        "TR_transform": {
            "levels_radius": levels.radius,
            "switch_to_inflation": difference,
            "LM_search": checks,
            "unit_roots": gates,
        },
        "proxy": proxy,
        "elapsed_seconds": time.monotonic() - began,
        "paid_calls": 0,
        "bands": (
            "recursive Kilian iid; plain/FEVD/HD moving-block robustness; LP direct outcome HAC"
        ),
        "scope_cuts": [
            "No new regime-specific historical decompositions; G2 retained privately",
            "No VECM; approved cumulative LP pass-through fallback",
        ],
    }
    (root / "results").mkdir(exist_ok=True)
    pd.DataFrame(irfs).to_csv(root / "results/g3_irfs.csv", index=False)
    pd.DataFrame(shares).to_csv(root / "results/g3_fevd.csv", index=False)
    pd.DataFrame(hds).to_csv(root / "results/g3_history_annual.csv", index=False)
    (root / "results/g3_summary.json").write_text(json.dumps(summary, indent=2))
    (directory / "manifest.json").write_text(json.dumps(summary, indent=2))
    return summary


def proxy_run(root, frame, c, irfs, directory):
    import openpyxl  # type: ignore[import-untyped]

    content = Client(root).get(
        "EA_MPD", "https://www.ecb.europa.eu/pub/pdf/annex/Dataset_EA-MPD.xlsx"
    )
    path = directory / "EA-MPD.xlsx"
    path.write_bytes(content)
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(workbook["Monetary Event Window"].iter_rows(max_col=46, values_only=True))
    header = list(rows[0])
    col = header.index("OIS_2Y")
    events = []
    for row in rows[1:]:
        if row[0] is None or row[col] is None:
            continue
        date = (
            pd.to_datetime(row[0], format="%d/%m/%Y")
            if isinstance(row[0], str)
            else pd.Timestamp(row[0])
        )
        events.append((date.to_period("M"), float(row[col])))
    # Zero only for known non-event months INSIDE the database's observed history.
    z = pd.Series([v for _, v in events], index=[t for t, _ in events]).groupby(level=0).sum()
    z = z.reindex(pd.period_range("1999-01", "2025-10", freq="M"), fill_value=0)
    spec = dict(c["models"][0], end="2025-10")
    y, d, labels, index = prepare(frame, spec, False)
    m, _, checks = choose_lag(y, d)
    instrument = z.reindex(index[m.start :]).to_numpy()
    impact, info = proxy_impact(m, instrument, 4)
    info.update(
        sample=["2004-09", "2025-10"],
        window="Monetary Event Window",
        column="OIS_2Y",
        choice=(
            "Combined decision/conference window matches policy indicator; "
            "may contain information shocks"
        ),
        raw_sha256=hashlib.sha256(content).hexdigest(),
        LM_search=checks,
        later_months="missing, not zero",
        terms="ECB attribution/modification disclosure; private workbook",
    )
    if info["status"] == "identified_conditional":
        point = ma(m, 36) @ impact
        rng = np.random.default_rng(c["seed"])
        draws = []
        # Paired residual/instrument circular block resampling preserves instrument covariance.
        for _ in range(499):
            starts = rng.integers(0, len(instrument), size=(len(instrument) + 5) // 6)
            idx = np.concatenate([(i + np.arange(6)) % len(instrument) for i in starts])[
                : len(instrument)
            ]
            u = m.resid[idx]
            zz = instrument[idx]
            test = replace(m, resid=u)
            a, _ = proxy_impact(test, zz, 4)
            if np.isfinite(a).all():
                draws.append(ma(m, 36) @ a)
        info["bootstrap_successful"] = len(draws)
        info["uncertainty"] = (
            "paired residual-IV blocks, conditional on estimated VAR slopes; "
            "weak draws omitted and counted"
        )
        if len(draws) >= 100:
            irfs += table_rows(
                "EA_proxy_overlap", labels, point, quantiles(np.array(draws)), "proxy"
            )
        else:
            info["status"] = "insufficient_bootstrap"
            info["fallback"] = "LP + signs"
    else:
        info["fallback"] = "LP + sign restrictions; no proxy IRF under F gate"
    return info
