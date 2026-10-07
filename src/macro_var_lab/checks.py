"""Data QA and unit-root diagnostics; tests never change baseline transforms."""

import warnings
from typing import Any

import numpy as np
import pandas as pd
from arch.unitroot import PhillipsPerron
from statsmodels.tsa.stattools import adfuller, kpss, zivot_andrews


def longest_complete(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    full = series.reindex(pd.period_range(series.index.min(), series.index.max(), freq="M"))
    groups = full.notna().ne(full.notna().shift()).cumsum()
    parts = [part for _, part in full.groupby(groups) if part.notna().all()]
    return max(parts, key=len) if parts else full.iloc[:0]


def coverage(series: pd.Series, start: str, end: str) -> dict[str, Any]:
    target = series.reindex(pd.period_range(start, end, freq="M"))
    observed = target.dropna()
    differences = target.diff().dropna()
    deviation = float(differences.std()) if len(differences) > 1 else 0.0
    flags = differences.index[np.abs(differences - differences.mean()) > 6 * deviation]
    return {
        "target_start": start,
        "target_end": end,
        "target_months": len(target),
        "observed_months": int(target.notna().sum()),
        "missing_months": int(target.isna().sum()),
        "missing_dates": [str(x) for x in target.index[target.isna()]],
        "first_observed": str(observed.index.min()) if len(observed) else None,
        "last_observed": str(observed.index.max()) if len(observed) else None,
        "nonpositive_months": int((observed <= 0).sum()),
        "six_sd_change_flags": [str(x) for x in flags],
        "outlier_flags_are_not_deletions": True,
        "interpolated": False,
    }


def diagnostics(series: pd.Series) -> dict[str, Any]:
    values = longest_complete(series)
    report: dict[str, Any] = {
        "observations": len(values),
        "start": str(values.index.min()) if len(values) else None,
        "end": str(values.index.max()) if len(values) else None,
        "sample_rule": "longest contiguous complete monthly block; never compress gaps",
        "baseline_transform_changed": False,
    }
    if len(values) < 60 or values.nunique() < 3:
        return report | {"status": "insufficient_sample"}
    for deterministic in ("c", "ct"):
        tests = {
            "ADF": lambda d=deterministic: adfuller(
                values.to_numpy(), maxlag=12, regression=d, autolag="BIC"
            ),
            "KPSS": lambda d=deterministic: kpss(values.to_numpy(), regression=d, nlags="auto"),
            "PP": lambda d=deterministic: PhillipsPerron(values.to_numpy(), trend=d),
            "ZA": lambda d=deterministic: zivot_andrews(
                values.to_numpy(), maxlag=12, regression=d, autolag="BIC", trim=0.15
            ),
        }
        for name, calculate in tests.items():
            key = f"{name}_{deterministic}"
            try:
                with warnings.catch_warnings(record=True) as messages:
                    warnings.simplefilter("always")
                    result = calculate()
                    entry: dict[str, Any]
                    if name == "PP":
                        entry = {
                            "statistic": float(result.stat),
                            "pvalue": float(result.pvalue),
                            "lags": int(result.lags),
                        }
                    else:
                        entry = {
                            "statistic": float(result[0]),
                            "pvalue": float(result[1]),
                            "lags": int(result[2] if name != "ZA" else result[3]),
                        }
                        if name == "ZA":
                            entry["break_month"] = str(values.index[result[4]])
                    entry["warnings"] = [str(x.message) for x in messages]
                    report[key] = entry
            except (ValueError, np.linalg.LinAlgError) as error:
                report[key] = {"status": "failed", "error_class": type(error).__name__}
    return report | {
        "status": "diagnostics_only",
        "nulls": {
            "ADF_PP": "unit root",
            "KPSS": "level/trend stationarity",
            "ZA": "unit root without a structural break; approximate single-break test",
        },
    }


def panel_sample(panel: pd.DataFrame, columns: list[str], start: str, end: str) -> dict:
    absent = [column for column in columns if column not in panel]
    if absent:
        return {"status": "blocked", "absent_columns": absent}
    target = panel[columns].reindex(pd.period_range(start, end, freq="M"))
    complete = target.notna().all(axis=1)
    usable = longest_complete(pd.Series(np.where(complete, 1.0, np.nan), index=target.index))
    return {
        "status": "complete_target" if complete.all() else "coverage_gap",
        "requested_start": start,
        "requested_end": end,
        "target_months": len(target),
        "complete_months": int(complete.sum()),
        "missing_dates": [str(x) for x in target.index[~complete]],
        "longest_complete_start": str(usable.index.min()) if len(usable) else None,
        "longest_complete_end": str(usable.index.max()) if len(usable) else None,
        "longest_complete_months": len(usable),
        "silently_trimmed": False,
    }


def supplementary(monthly: pd.DataFrame, end: str) -> tuple[dict, dict]:
    """Aggregate growth preservation and policy-indicator checks, never splice."""
    bridges = {}
    for label, old, new in [
        ("headline", "tr_cpi_old", "tr_cpi"),
        ("core_b", "tr_core_b_old", "tr_core_b"),
        ("core_c", "tr_core_c_old", "tr_core_c"),
    ]:
        if not {old, new} <= set(monthly):
            continue
        pair = monthly[[old, new]].dropna()
        if pair.empty:
            continue
        full = pair.reindex(pd.period_range(pair.index.min(), pair.index.max(), freq="M"))
        differences = (
            pd.DataFrame(np.log(full.to_numpy()), index=full.index, columns=full.columns).diff()
            * 100
        )
        gap = (differences[new] - differences[old]).dropna()
        target = monthly[new].reindex(pd.period_range("2006-01", end, freq="M"))
        bridges[label] = {
            "overlap_start": str(pair.index.min()),
            "overlap_end": str(pair.index.max()),
            "max_abs_monthly_log_growth_gap_pp": float(gap.abs().max()),
            "mean_abs_monthly_log_growth_gap_pp": float(gap.abs().mean()),
            "no_splice_needed_for_target": bool(target.notna().all()),
        }
    if not {"tr_aofm", "tr_announced"} <= set(monthly):
        return bridges, {"status": "unavailable"}
    pair = monthly.loc["2006-01":end, ["tr_aofm", "tr_announced"]].dropna()
    if pair.empty:
        return bridges, {"status": "unavailable"}
    gap = pair.tr_aofm - pair.tr_announced
    return bridges, {
        "overlap_start": str(pair.index.min()),
        "overlap_end": str(pair.index.max()),
        "overlap_months": len(pair),
        "mean_abs_gap_pp": float(gap.abs().mean()),
        "max_abs_gap_pp": float(gap.abs().max()),
        "mean_signed_gap_pp": float(gap.mean()),
        "indicators_not_identical": bool((gap.abs() > 1e-6).any()),
        "announced_months": int(monthly.tr_announced.notna().sum()),
        "known_cut": "2010-05-20",
        "2018_simplification": "2018-06-01",
        "AOFM_substituted": False,
    }
