"""Offline G2 estimates, guarded TR transform decision, resumable joint bootstrap."""

import hashlib
import json
import platform
import resource
import subprocess
import time
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from statsmodels.tsa.vector_ar.vecm import VECM, coint_johansen

from macro_var_lab.checks import diagnostics
from macro_var_lab.identification import displayed, hac_bands, lp_inputs, projections, rotations
from macro_var_lab.var import (
    deterministic,
    fevd,
    fit,
    history,
    recursive,
    residual_checks,
    select,
    simulate,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unit_root_gate(frame: pd.DataFrame) -> dict:
    result = {}
    for name in ["tr_cpi", "usdtry", "tr_reer"]:
        x = frame.loc["2006-01":"2026-07", name]
        level = diagnostics(x)
        difference = diagnostics(x.diff().dropna())
        i1 = (
            level["ADF_ct"]["pvalue"] > 0.05
            and level["PP_ct"]["pvalue"] > 0.05
            and level["KPSS_ct"]["pvalue"] < 0.05
            and difference["ADF_c"]["pvalue"] < 0.05
            and difference["PP_c"]["pvalue"] < 0.05
            and difference["KPSS_c"]["pvalue"] >= 0.05
        )
        i2 = (
            difference["ADF_c"]["pvalue"] >= 0.05
            and difference["PP_c"]["pvalue"] >= 0.05
            and difference["KPSS_c"]["pvalue"] < 0.05
        )
        result[name] = {
            "level": level,
            "first_difference": difference,
            "I1_established_by_agreement_rule": bool(i1),
            "I2_compatible_by_agreement_rule": bool(i2),
            "not_proof_of_integration_order": True,
        }
    return result


def vecm_pass(frame: pd.DataFrame, gates: dict) -> dict:
    if not all(item["I1_established_by_agreement_rule"] for item in gates.values()):
        return {
            "status": "not_estimated",
            "reason": "I(1) agreement conditions not established for every variable",
            "failed_variables": [
                name for name, row in gates.items() if not row["I1_established_by_agreement_rule"]
            ],
            "no_Johansen_run": True,
            "no_silent_relaxation": True,
        }
    data = frame.loc["2006-01":"2026-07", ["tr_cpi", "usdtry", "tr_reer"]]
    model, ic = select(data.to_numpy(), np.ones((len(data), 1)), 12)
    johansen = coint_johansen(data.to_numpy(), 0, model.p - 1)
    rank = 0
    for stat, critical in zip(johansen.lr1, johansen.cvt[:, 1], strict=True):
        if stat <= critical:
            break
        rank += 1
    result = {
        "trace_statistics": johansen.lr1.tolist(),
        "critical_95": johansen.cvt[:, 1].tolist(),
        "lag_levels": model.p,
        "rank_95": rank,
        "status": "Johansen_only",
        "lag_selection": ic,
        "deterministic": "constant, det_order=0; VECM restricted cointegration constant ci",
    }
    if 0 < rank < 3:
        fitted = VECM(
            data, k_ar_diff=model.p - 1, coint_rank=rank, deterministic="ci", seasons=12
        ).fit()
        result.update(
            status="estimated",
            alpha=fitted.alpha.tolist(),
            beta=fitted.beta.tolist(),
            note="Cointegration associations, not identified causal exchange-rate pass-through",
        )
    return result


def prepare(
    frame: pd.DataFrame, spec: dict, difference: bool, growth: bool = False
) -> tuple[np.ndarray, np.ndarray, list[str], pd.PeriodIndex]:
    source = (
        ["brent", "vix", "ea_ip", spec["price"], spec["policy"], "eurusd"]
        if spec["area"] == "EA"
        else ["brent", "vix", "fedfunds", "tr_ip", spec["price"], spec["policy"], "usdtry"]
    )
    labels = (
        ["brent", "vix", "activity", "price", "policy", "fx"]
        if spec["area"] == "EA"
        else ["brent", "vix", "fedfunds", "activity", "price", "policy", "fx"]
    )
    data = frame[source].copy()
    data.columns = labels
    if difference:
        data["price"] = data.price.diff()
    if growth:
        for name in ["brent", "vix", "activity", "fx"]:
            data[name] = data[name].diff()
    data = data.loc[spec["start"] : spec["end"]]
    if data.isna().any().any():
        raise ValueError("Requested sample has missing observations; no silent trimming")
    return (
        data.to_numpy(),
        deterministic(pd.PeriodIndex(data.index, freq="M"), "overnight" in spec["policy"]),
        labels,
        pd.PeriodIndex(data.index, freq="M"),
    )


def quantiles(draws: np.ndarray) -> dict:
    return {
        name: np.quantile(draws, probability, axis=0)
        for name, probability in [("lo90", 0.05), ("lo68", 0.16), ("hi68", 0.84), ("hi90", 0.95)]
    }


def recent_lp(model, offset: int, config: dict, hac: bool = True, normalize: bool = True):
    """Four domestic outcomes, one lag, full-sample identified shock; no short VAR."""
    _, impact, eps = recursive(model, model.y.shape[1] - 2, 0)
    shock = np.full(len(model.y), np.nan)
    shock[model.start :] = eps[:, -2] * impact[-2, -2]
    y = model.y[offset:, 3:]
    x = np.column_stack([model.deterministic[offset + 1 :], y[:-1]])
    point, se, counts = lp_inputs(
        y, x, 1, shock[offset + 1 :], 2, config["horizon"], config["min_lp_residual_df"], hac
    )
    if normalize:
        scale = point[0, 2]
        if not np.isfinite(scale) or abs(scale) < 1e-8:
            raise ValueError("Recent LP impact normalization is weak or unavailable")
        point, se = point / scale, se / abs(scale)
    return point, se, counts


def bootstrap(
    model,
    labels,
    policy,
    config,
    cache: Path,
    job_seed: int,
    price_difference: bool,
    growth: bool,
    want_history: bool,
    recent_offset: int | None = None,
) -> tuple[dict, dict]:
    target = config["bootstrap_draws"]
    h = config["horizon"]
    cached = {}
    if cache.exists():
        with np.load(cache) as data:
            cached = {name: data[name] for name in data.files}
    points = list(cached.get("var", []))
    lps = list(cached.get("lp", []))
    shares = list(cached.get("fevd", []))
    histories = list(cached.get("history", []))
    radii = list(cached.get("radius", []))
    recent = list(cached.get("recent", []))
    failures = int(cached.get("failures", 0))
    attempts = int(cached.get("attempts", len(points)))
    while len(points) < target and attempts < target + max(20, target // 10):
        rng = np.random.default_rng(
            np.random.SeedSequence([config["seed"], job_seed, attempts + 1])
        )
        attempts += 1
        try:
            generated = simulate(model, rng, config["bootstrap_block"])
            draw = fit(generated, model.deterministic, model.p, model.external)
            response, _, _ = recursive(draw, policy, h)
            lp, _, _ = projections(draw, policy, h, config["min_lp_residual_df"], False)
            share = fevd(draw, h)
            if not np.isfinite(response).all() or not np.isfinite(share).all():
                raise ValueError("Nonfinite draw")
            if want_history:
                # Parameter draw applied to actual historical observations.
                actual = replace(
                    draw, y=model.y, x=model.x, resid=model.y[model.start :] - model.x @ draw.beta
                )
                base, effect, error = history(actual)
                if error > 1e-5:
                    raise ValueError("Historical accounting does not reconstruct")
                contribution = effect[:, labels.index("price"), policy]
                if not price_difference:
                    contribution = np.diff(contribution, prepend=0)
            if recent_offset is not None:
                short, _, _ = recent_lp(draw, recent_offset, config, False)
                recent.append(displayed(short, labels[3:], price_difference))
            points.append(displayed(response, labels, price_difference, growth))
            lps.append(displayed(lp, labels, price_difference, growth))
            shares.append(share)
            radii.append(draw.radius)
            if want_history:
                histories.append(contribution)
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            failures += 1
        if len(points) % 25 == 0 or len(points) == target:
            cache.parent.mkdir(parents=True, exist_ok=True)
            with cache.with_suffix(".tmp").open("wb") as stream:
                np.savez_compressed(
                    stream,
                    var=np.array(points),
                    lp=np.array(lps),
                    fevd=np.array(shares),
                    history=np.array(histories),
                    radius=np.array(radii),
                    attempts=attempts,
                    failures=failures,
                    recent=np.array(recent),
                )
            cache.with_suffix(".tmp").replace(cache)
    arrays = {
        "var": np.array(points[:target]),
        "lp": np.array(lps[:target]),
        "fevd": np.array(shares[:target]),
        "history": np.array(histories[:target]),
        "recent": np.array(recent[:target]),
    }
    metadata = {
        "requested": target,
        "successful": len(arrays["var"]),
        "attempts": attempts,
        "failed": failures,
        "unstable_retained": int(np.sum(np.array(radii[:target]) >= 1)),
        "method": (
            "circular moving-block residual vector resampling, block 6; "
            "fixed lag/deterministic terms; refit/re-identify each draw"
        ),
        "bands": "pointwise percentile 68/90; LP re-estimates shock and outcome jointly",
        "not_simultaneous_bands": True,
        "conditional_on_transform_and_lag_selection": True,
        "status": "complete" if len(arrays["var"]) == target else "incomplete",
    }
    return arrays, metadata


def run(root: Path, config_path: Path, pilot: bool = False) -> dict:
    began = time.monotonic()
    config = yaml.safe_load(config_path.read_text())
    inputs = root / "data/processed/baseline_levels.csv"
    frame = pd.read_csv(inputs, index_col=0)
    frame.index = pd.PeriodIndex(frame.index, freq="M")
    source = json.loads((root / "results/g1_data_checks.json").read_text())
    if source["status"] != "data_checked":
        raise ValueError("Approved G1 data required")
    gates = unit_root_gate(frame)
    baseline_tr = next(s for s in config["models"] if s["name"] == "TR_baseline")
    y, d, labels, index = prepare(frame, baseline_tr, False)
    first, ic = select(y, d, config["lag_max"], 3)
    switch = bool(first.radius >= 1 or gates["tr_cpi"]["I2_compatible_by_agreement_rule"])
    decision = {
        "levels_lag": first.p,
        "levels_radius": first.radius,
        "levels_stable": first.radius < 1,
        "switch_to_inflation": switch,
        "trigger": "levels instability"
        if first.radius >= 1
        else "I2 agreement rule"
        if switch
        else "none",
        "preserved_levels_diagnostics": residual_checks(first, labels),
        "levels_lag_selection": ic,
        "no_extra_transform_to_force_stability": True,
        "baseline_CPI_unit_roots": {
            "sample": [baseline_tr["start"], baseline_tr["end"]],
            "log_level": diagnostics(
                frame.loc[baseline_tr["start"] : baseline_tr["end"], "tr_cpi"]
            ),
            "first_difference": diagnostics(
                frame.tr_cpi.diff().loc[baseline_tr["start"] : baseline_tr["end"]]
            ),
        },
    }
    codes = {str(path.relative_to(root)): digest(path) for path in (root / "src").rglob("*.py")}
    contract = {
        "input_sha256": digest(inputs),
        "seed": config["seed"],
        "config": {k: v for k, v in config.items() if k != "bootstrap_draws"},
        "code": codes,
    }
    token = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    directory = root / "runs" / ("g2_" + token[:16])
    directory.mkdir(parents=True, exist_ok=True)
    models = config["models"][:2] if pilot else config["models"]
    if not pilot:
        for number, (start, end) in enumerate(config["regimes"][:2], 1):
            models = models + [
                dict(baseline_tr, name=f"TR_regime_{number}", start=start, end=end, kind="regime")
            ]
    if pilot:
        config = dict(config, bootstrap_draws=20)
    all_rows = []
    all_hac = []
    fevd_rows = []
    lag_rows = []
    records = {}
    for spec in models:
        name = spec["name"]
        job_seed = int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big")
        difference = (
            switch and spec["area"] == "TR" and spec["kind"] != "levels_comparison"
        ) or spec["kind"] == "growth_robustness"
        growth = spec["kind"] == "growth_robustness"
        y, d, labels, index = prepare(frame, spec, difference, growth)
        external = 3 if spec["area"] == "TR" else 0
        maxlag = min(config["lag_max"], 2 if spec["kind"] == "regime" else config["lag_max"])
        model, ic = select(y, d, maxlag, external)
        policy = labels.index("policy")
        price = labels.index("price")
        response, impact, eps = recursive(model, policy, config["horizon"])
        lp, se, counts = projections(model, policy, config["horizon"], config["min_lp_residual_df"])
        sign, sign_meta = rotations(
            model,
            policy,
            price,
            config["horizon"],
            np.random.default_rng(np.random.SeedSequence([config["seed"], job_seed, 0])),
            config["sign_draws"],
            config["sign_max_attempts"],
            config["sign_rate_floor_sd"],
            difference,
        )
        cache = directory / name / "bootstrap.npz"
        recent_offset = (
            int(np.flatnonzero(index == pd.Period(config["regimes"][2][0]))[0])
            if name == "TR_baseline"
            else None
        )
        arrays, boot_meta = bootstrap(
            model,
            labels,
            policy,
            config,
            cache,
            job_seed,
            difference,
            growth,
            spec["kind"] == "baseline",
            recent_offset,
        )
        point = displayed(response, labels, difference, growth)
        lp_point = displayed(lp, labels, difference, growth)
        series_result = {
            "recursive": (point, quantiles(arrays["var"])),
            "LP_joint_bootstrap": (lp_point, {}),
        }
        # Drop entirely unestimable horizons explicitly; avoid NaN quantile warnings.
        lp_bands = {key: np.full_like(lp_point, np.nan) for key in ["lo90", "lo68", "hi68", "hi90"]}
        for h in range(config["horizon"] + 1):
            if counts[h]:
                q = quantiles(arrays["lp"][:, h])
                for key in lp_bands:
                    lp_bands[key][h] = q[key]
        series_result["LP_joint_bootstrap"] = (lp_point, lp_bands)
        if len(sign):
            shown = np.array([displayed(draw, labels, difference, growth) for draw in sign])
            series_result["sign_rotation_set"] = (np.median(shown, axis=0), quantiles(shown))
        for method, (point_values, bands) in series_result.items():
            for h in range(config["horizon"] + 1):
                for j, label in enumerate(labels):
                    all_rows.append(
                        {
                            "model": name,
                            "method": method,
                            "horizon": h,
                            "variable": label,
                            "estimate": float(point_values[h, j]),
                            **{key: float(value[h, j]) for key, value in bands.items()},
                            "unit": "percent log price level"
                            if label == "price"
                            else "pp"
                            if label in ("policy", "fedfunds")
                            else "log percent"
                            if label != "vix"
                            else "log units",
                            "uncertainty": "rotation spread, not CI"
                            if method == "sign_rotation_set"
                            else "pointwise bootstrap",
                        }
                    )
        # Native LP HAC data have not been accumulated; report inflation-native SE honestly.
        hac_table = []
        for h in range(config["horizon"] + 1):
            for j, label in enumerate(labels):
                hac_table.append(
                    {
                        "horizon": h,
                        "variable": label,
                        "estimate": lp[h, j],
                        "HAC_se": se[h, j],
                        "nobs": counts[h],
                        **{key: value[h, j] for key, value in hac_bands(lp, se).items()},
                    }
                )
        all_hac.extend([dict(model=name, **row) for row in hac_table])
        if name == "TR_baseline" and not pilot:
            assert recent_offset is not None
            short, short_se, short_counts = recent_lp(model, recent_offset, config)
            short_point = displayed(short, labels[3:], difference)
            short_bands = {
                key: np.full_like(short_point, np.nan) for key in ["lo90", "lo68", "hi68", "hi90"]
            }
            for h in range(config["horizon"] + 1):
                if short_counts[h]:
                    for key, value in quantiles(arrays["recent"][:, h]).items():
                        short_bands[key][h] = value
                for j, label in enumerate(labels[3:]):
                    all_rows.append(
                        {
                            "model": "TR_regime_3_LP",
                            "method": "LP_joint_bootstrap",
                            "horizon": h,
                            "variable": label,
                            "estimate": float(short_point[h, j]),
                            **{key: float(value[h, j]) for key, value in short_bands.items()},
                            "unit": "percent log price level"
                            if label == "price"
                            else "pp"
                            if label == "policy"
                            else "log percent",
                            "uncertainty": "pointwise bootstrap; full-sample shock re-estimated",
                        }
                    )
                    all_hac.append(
                        {
                            "model": "TR_regime_3_LP",
                            "horizon": h,
                            "variable": label,
                            "estimate": float(short[h, j]),
                            "HAC_se": float(short_se[h, j]),
                            "nobs": int(short_counts[h]),
                            **{
                                key: float(value[h, j])
                                for key, value in hac_bands(short, short_se).items()
                            },
                        }
                    )
            records["TR_regime_3_LP"] = {
                "spec": {
                    "start": config["regimes"][2][0],
                    "end": config["regimes"][2][1],
                    "kind": "LP_only",
                },
                "variables": labels[3:],
                "months": len(index) - recent_offset,
                "lag": 1,
                "no_VAR_estimated": True,
                "price_transform": "monthly inflation" if difference else "100 log level",
                "LP_nobs_by_horizon": short_counts.tolist(),
                "shock_source": "TR_baseline full-sample recursive shock; retrospective",
                "normalization": "divide by recent LP policy impact in point and every draw",
                "original_policy_impact": float(
                    recent_lp(model, recent_offset, config, False, False)[0][0, 2]
                ),
                "HAC_note": (
                    "conditional on point-estimated impact divisor; "
                    "joint bootstrap propagates divisor uncertainty"
                ),
                "bootstrap": boot_meta,
                "limited_horizons_are_not_filled": True,
            }
        job = directory / name
        job.mkdir(exist_ok=True)
        pd.DataFrame(hac_table).to_csv(job / "lp_native_hac.csv", index=False)
        for row in ic:
            lag_rows.append(dict(model=name, **row))
        shares = fevd(model, config["horizon"])
        share_bands = quantiles(arrays["fevd"])
        for h in range(config["horizon"]):
            for j, label in enumerate(labels):
                for shock, shock_label in enumerate(labels):
                    fevd_rows.append(
                        {
                            "model": name,
                            "horizon": h + 1,
                            "variable": label,
                            "shock": shock_label,
                            "price_unit": "monthly inflation"
                            if difference
                            else "100 log price level",
                            "share": float(shares[h, j, shock]),
                            **{
                                key: float(value[h, j, shock]) for key, value in share_bands.items()
                            },
                        }
                    )
        base, effect, error = history(model)
        inflation = (
            effect[:, price, :]
            if difference
            else np.diff(effect[:, price, :], axis=0, prepend=np.zeros((1, len(labels))))
        )
        baseline = base[:, price] if difference else np.diff(base[:, price], prepend=base[0, price])
        observed = y[:, price] if difference else np.diff(y[:, price], prepend=y[0, price])
        table = pd.DataFrame(inflation, index=index, columns=labels)
        table["initial_deterministic"] = baseline
        table["reconstruction"] = baseline + inflation.sum(axis=1)
        table.iloc[model.start :].to_csv(job / "inflation_history_private.csv")
        np.savez_compressed(
            job / "point.npz",
            native_irf=response,
            native_lp=lp,
            impact=impact,
            innovations=eps,
            residuals=model.resid,
            coefs=model.coefs,
            beta=model.beta,
            index=np.array([str(x) for x in index]),
        )
        records[name] = {
            "spec": spec,
            "variables": labels,
            "months": len(y),
            "nobs": len(model.resid),
            "lag": model.p,
            "price_transform": "monthly inflation" if difference else "100 log level",
            "growth_robustness": growth,
            "rates_kept_in_levels": True,
            "external_block_equations": external,
            "lag_selection": ic,
            "residual_diagnostics": residual_checks(model, labels),
            "bootstrap": boot_meta,
            "sign_restrictions": sign_meta,
            "LP_nobs_by_horizon": counts.tolist(),
            "LP_HAC_bandwidth": "h+1; Bartlett, finite-sample df adjustment",
            "HD_level_reconstruction_error": error,
            "HD_inflation_reconstruction_error": float(
                np.abs(table.reconstruction.iloc[model.start :] - observed[model.start :]).max()
            ),
            "no_missingness_trim": True,
            "transition_dummy": "2019-10 level shift" if "overnight" in spec["policy"] else None,
        }
        print(
            json.dumps(
                {
                    "model": name,
                    "lag": model.p,
                    "radius": model.radius,
                    "bootstrap": boot_meta["successful"],
                    "sign": sign_meta["accepted"],
                }
            ),
            flush=True,
        )
    summary = {
        "gate": "G2",
        "kind": "pilot" if pilot else "results_pending_review",
        "analysis_id": directory.name,
        "G1_run": source["run"],
        "seed": config["seed"],
        "TR_transform_decision": decision,
        "unit_root_tests": gates,
        "models": records,
        "vecm": {"status": "deferred_in_pilot"} if pilot else vecm_pass(frame, gates),
        "elapsed_seconds": time.monotonic() - began,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "paid_calls": 0,
        "no_publication": True,
        "bootstrap_draws": config["bootstrap_draws"],
        "contract": contract,
    }
    path = root / "results" / ("g2_pilot.json" if pilot else "g2_summary.json")
    path.write_text(json.dumps(summary, indent=2) + "\n")
    if not pilot:
        pd.DataFrame(all_rows).to_csv(root / "results/g2_irfs.csv", index=False)
        pd.DataFrame(fevd_rows).to_csv(root / "results/g2_fevd.csv", index=False)
        pd.DataFrame(lag_rows).to_csv(root / "results/g2_lag_selection.csv", index=False)
        pd.DataFrame(all_hac).to_csv(root / "results/g2_lp_hac.csv", index=False)
    manifest = {
        "contract": contract,
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root)),
        "python": platform.python_version(),
        "libraries": {
            name: version(name)
            for name in ["numpy", "pandas", "scipy", "statsmodels", "arch", "matplotlib"]
        },
        "config_actual": config,
        "summary_sha256": digest(path),
        "source_manifest": source["run"],
        "network_calls": 0,
        "paid_calls": 0,
    }
    (directory / ("pilot_manifest.json" if pilot else "manifest.json")).write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return summary
