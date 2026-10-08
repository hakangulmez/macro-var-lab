"""OLS VARs with explicit deterministic terms and optional external block exclusion."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import chi2, jarque_bera  # type: ignore[import-untyped]


@dataclass
class Fit:
    y: np.ndarray
    deterministic: np.ndarray
    p: int
    external: int
    start: int
    x: np.ndarray
    beta: np.ndarray
    masks: list[np.ndarray]
    resid: np.ndarray
    sigma: np.ndarray
    coefs: np.ndarray
    nparams: int

    @property
    def radius(self) -> float:
        k = self.y.shape[1]
        companion = np.zeros((k * self.p, k * self.p))
        companion[:k] = np.hstack(list(self.coefs))
        if self.p > 1:
            companion[k:, :-k] = np.eye(k * (self.p - 1))
        return float(np.abs(np.linalg.eigvals(companion)).max())


def deterministic(index: pd.PeriodIndex, transition: bool = False) -> np.ndarray:
    columns = [np.ones(len(index))] + [
        (index.month == month).astype(float) for month in range(2, 13)
    ]
    if transition:
        columns += [(index >= pd.Period("2019-10")).astype(float)]
    return np.column_stack(columns)


def fit(y: np.ndarray, d: np.ndarray, p: int, external: int = 0, start: int | None = None) -> Fit:
    """Fit on a complete consecutive array; comparable IC windows use explicit start."""
    if not np.isfinite(y).all() or not np.isfinite(d).all() or p < 1:
        raise ValueError("Finite consecutive observations and positive lag required")
    t, k = y.shape
    start = p if start is None else start
    if start < p or len(d) != t:
        raise ValueError("Invalid alignment")
    x = np.column_stack([d[start:]] + [y[start - lag : t - lag] for lag in range(1, p + 1)])
    beta = np.zeros((x.shape[1], k))
    masks = []
    for equation in range(k):
        mask = np.ones(x.shape[1], dtype=bool)
        if equation < external:
            for lag in range(p):
                mask[d.shape[1] + lag * k + external : d.shape[1] + (lag + 1) * k] = False
        if len(x) - mask.sum() < 10 or np.linalg.matrix_rank(x[:, mask]) < mask.sum():
            raise ValueError("Insufficient residual degrees of freedom or rank deficient design")
        beta[mask, equation] = np.linalg.lstsq(x[:, mask], y[start:, equation], rcond=None)[0]
        masks.append(mask)
    resid = y[start:] - x @ beta
    # Common ML divisor: PSD covariance even with different constrained equation dfs.
    sigma = resid.T @ resid / len(resid)
    if np.linalg.slogdet(sigma)[0] <= 0:
        raise ValueError("Nonpositive residual covariance")
    coefs = np.array(
        [beta[d.shape[1] + lag * k : d.shape[1] + (lag + 1) * k].T for lag in range(p)]
    )
    return Fit(
        y,
        d,
        p,
        external,
        start,
        x,
        beta,
        masks,
        resid,
        sigma,
        coefs,
        int(sum(m.sum() for m in masks)),
    )


def select(y: np.ndarray, d: np.ndarray, maxlag: int, external: int = 0) -> tuple[Fit, list[dict]]:
    """Common IC sample across feasible lags; refit selected BIC lag on full sample."""
    feasible = min(maxlag, max(1, (len(y) - d.shape[1] - 10) // (y.shape[1] + 1)))
    rows = []
    for p in range(1, feasible + 1):
        model = fit(y, d, p, external, start=feasible)
        n = len(model.resid)
        logdet = float(np.linalg.slogdet(model.sigma)[1])
        rows.append(
            {
                "lag": p,
                "nobs_common": n,
                "nparams": model.nparams,
                "AIC": logdet + 2 * model.nparams / n,
                "BIC": logdet + np.log(n) * model.nparams / n,
                "HQ": logdet + 2 * np.log(np.log(n)) * model.nparams / n,
            }
        )
    best = min(rows, key=lambda row: row["BIC"])["lag"]
    return fit(y, d, int(best), external), rows


def ma(model: Fit, horizon: int) -> np.ndarray:
    k = model.y.shape[1]
    response = np.zeros((horizon + 1, k, k))
    response[0] = np.eye(k)
    for h in range(1, horizon + 1):
        for lag in range(1, min(model.p, h) + 1):
            response[h] += model.coefs[lag - 1] @ response[h - lag]
    return response


def recursive(model: Fit, policy: int, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    impact = np.linalg.cholesky(model.sigma)
    response = ma(model, horizon) @ impact
    if impact[policy, policy] <= 1e-10:
        raise ValueError("Weak policy-shock normalization")
    # A rate unit is one percentage point = 100 basis points.
    shock = response[:, :, policy] / impact[policy, policy]
    eps = np.linalg.solve(impact, model.resid.T).T
    return shock, impact, eps


def fevd(model: Fit, horizon: int) -> np.ndarray:
    response = ma(model, horizon - 1) @ np.linalg.cholesky(model.sigma)
    numerator = np.cumsum(response**2, axis=0)
    return numerator / numerator.sum(axis=2, keepdims=True)


def history(model: Fit) -> tuple[np.ndarray, np.ndarray, float]:
    """Exact conditional deterministic/initial-history + all structural shocks."""
    _, impact, eps = recursive(model, model.y.shape[1] - 2, 0)
    t, k = model.y.shape
    effects = np.zeros((t, k, k))
    base = np.zeros((t, k))
    base[: model.start] = model.y[: model.start]
    nd = model.deterministic.shape[1]
    for time in range(model.start, t):
        base[time] = model.deterministic[time] @ model.beta[:nd]
        effects[time] = impact * eps[time - model.start][None, :]
        for lag in range(1, model.p + 1):
            base[time] += model.coefs[lag - 1] @ base[time - lag]
            effects[time] += model.coefs[lag - 1] @ effects[time - lag]
    error = float(np.abs(base + effects.sum(axis=2) - model.y).max())
    return base, effects, error


def simulate(model: Fit, rng: np.random.Generator, block: int = 6) -> np.ndarray:
    """Vector moving-block residual bootstrap, conditional on observed initial lags."""
    n = len(model.resid)
    starts = rng.integers(0, n, size=(n + block - 1) // block)
    indices = np.concatenate([(s + np.arange(block)) % n for s in starts])[:n]
    errors = (model.resid - model.resid.mean(axis=0))[indices]
    result = model.y.copy()
    nd = model.deterministic.shape[1]
    for time in range(model.start, len(result)):
        result[time] = model.deterministic[time] @ model.beta[:nd] + errors[time - model.start]
        for lag in range(1, model.p + 1):
            result[time] += model.coefs[lag - 1] @ result[time - lag]
    return result


def residual_checks(model: Fit, labels: list[str]) -> dict:
    """Equation-specific BG LM, marginal JB and conditional lag-exclusion Wald tests."""
    n, k = model.resid.shape
    out: dict = {
        "companion_spectral_radius": model.radius,
        "stable": model.radius < 1,
        "root_convention": "companion eigenvalue modulus < 1; not inverse roots",
        "BG_LM": {},
        "JB_marginal": {},
        "granger_policy_to": {},
    }
    for j, label in enumerate(labels):
        out["JB_marginal"][label] = {
            "statistic": float(jarque_bera(model.resid[:, j]).statistic),
            "pvalue": float(jarque_bera(model.resid[:, j]).pvalue),
        }
        checks: dict = {}
        for lag in [1, 6, 12]:
            x = model.x[lag:, model.masks[j]]
            z = np.column_stack([x] + [model.resid[lag - i : n - i] for i in range(1, lag + 1)])
            if len(z) - z.shape[1] < 10 or np.linalg.matrix_rank(z) < z.shape[1]:
                checks[str(lag)] = {"status": "insufficient_df_or_rank"}
                continue
            target = model.resid[lag:, j]
            err = target - z @ np.linalg.lstsq(z, target, rcond=None)[0]
            r2 = max(
                0.0,
                1 - float(err @ err) / float((target - target.mean()) @ (target - target.mean())),
            )
            stat = len(z) * r2
            df = lag * k
            checks[str(lag)] = {"statistic": stat, "df": df, "pvalue": float(chi2.sf(stat, df))}
        out["BG_LM"][label] = checks
    if "policy" not in labels:
        out["granger_status"] = "not_tested_no_policy_label"
        return out
    policy = labels.index("policy")
    out["granger_tested_variable"] = labels[policy]
    out["granger_policy_column"] = policy
    nd = model.deterministic.shape[1]
    for j, label in enumerate(labels):
        if j < model.external:
            out["granger_policy_to"][label] = {"status": "excluded_by_design"}
            continue
        x = model.x[:, model.masks[j]]
        cols = np.flatnonzero(model.masks[j])
        test = np.isin(cols, [nd + lag * k + policy for lag in range(model.p)])
        b = model.beta[model.masks[j], j]
        cov = (
            np.linalg.inv(x.T @ x) * (model.resid[:, j] @ model.resid[:, j]) / (len(x) - x.shape[1])
        )
        stat = float(b[test] @ np.linalg.solve(cov[np.ix_(test, test)], b[test]))
        out["granger_policy_to"][label] = {
            "statistic": stat,
            "df": model.p,
            "pvalue": float(chi2.sf(stat, model.p)),
            "not_causality_identification": True,
        }
    return out
