"""Reviewed lag rule, Kilian correction, cumulative LP and proxy identification."""

from dataclasses import replace

import numpy as np
from scipy.stats import chi2  # type: ignore[import-untyped]

from macro_var_lab.identification import lp_inputs
from macro_var_lab.var import Fit, fit, recursive, select, simulate


def system_lm(model: Fit, order: int = 1) -> dict:
    """Equation BG LM tests with all system residual lags; intersection rule."""
    u = model.resid
    n, k = u.shape
    x = model.x[order:]
    z = np.column_stack([x] + [u[order - lag : n - lag] for lag in range(1, order + 1)])
    # Block-exogenous equations have distinct regressor masks; test each restricted
    # equation, and report conservative minimum p-value across equations as fallback.
    pvalues = []
    for j in range(k):
        controls = model.x[order:, model.masks[j]]
        aug = np.column_stack([controls, z[:, model.x.shape[1] :]])
        if len(aug) - np.linalg.matrix_rank(aug) < 10:
            return {"status": "insufficient_df", "order": order, "pvalue": None}
        target = u[order:, j]
        e = target - aug @ np.linalg.lstsq(aug, target, rcond=None)[0]
        r2 = max(0.0, 1 - float(e @ e) / float((target - target.mean()) @ (target - target.mean())))
        pvalues.append(float(chi2.sf(len(e) * r2, k * order)))
    # Intersection criterion implements 'residuals pass': every equation must pass.
    return {
        "status": "tested",
        "order": order,
        "pvalue": min(pvalues),
        "equation_pvalues": pvalues,
        "criterion": "all equation BG LM p >= .05",
        "multiple_testing_note": "intersection of marginal tests; not a system LR test",
    }


def choose_lag(y, d, maxlag=12, external=0, force_bic=False):
    bic, ic = select(y, d, maxlag, external)
    checks = []
    for p in range(bic.p, maxlag + 1):
        try:
            model = fit(y, d, p, external)
            test = system_lm(model)
            checks.append({"lag": p, **test})
            if force_bic or (test["pvalue"] is not None and test["pvalue"] >= 0.05):
                return model, ic, checks
        except ValueError:
            checks.append({"lag": p, "status": "insufficient_df_or_rank", "pvalue": None})
    # Never silently call a failing specification LM-passing; explicit BIC fallback.
    return bic, ic, checks


def bias_adjust(model: Fit, bias: np.ndarray) -> tuple[Fit, dict]:
    if model.radius >= 1:
        return model, {"branch": "initially_nonstationary_unadjusted", "weight": 0.0}
    weight, delta = 1.0, 1.0
    nd, k = model.deterministic.shape[1], model.y.shape[1]
    for _ in range(102):
        coefs = model.coefs - weight * bias
        beta = model.beta.copy()
        for lag in range(model.p):
            beta[nd + lag * k : nd + (lag + 1) * k] = coefs[lag].T
        # Refit deterministic coefficients conditional on corrected autoregression.
        target = model.y[model.start :].copy()
        for lag in range(1, model.p + 1):
            target -= model.y[model.start - lag : len(model.y) - lag] @ coefs[lag - 1].T
        beta[:nd] = np.linalg.lstsq(model.deterministic[model.start :], target, rcond=None)[0]
        resid = model.y[model.start :] - model.x @ beta
        result = replace(
            model, beta=beta, coefs=coefs, resid=resid, sigma=resid.T @ resid / len(resid)
        )
        if result.radius < 1:
            return result, {"branch": "stationary_bias_adjusted", "weight": weight}
        weight *= delta
        delta = max(0.0, delta - 0.01)
    raise ValueError("Stationarity shrink did not terminate")


def kilian_draws(
    model: Fit, policy: int, horizon: int, seed: int, bias_draws: int, draws: int
) -> tuple[np.ndarray, dict]:
    """Bootstrap-after-bootstrap with reused first-stage bias (Kilian step 2b)."""
    rng = np.random.default_rng(seed)
    estimates = [
        fit(simulate(model, rng, 1), model.deterministic, model.p, model.external).coefs
        for _ in range(bias_draws)
    ]
    bias = np.mean(estimates, axis=0) - model.coefs
    generator, info = bias_adjust(model, bias)
    responses = []
    branches: dict[str, int] = {}
    for _ in range(draws):
        draw = fit(simulate(generator, rng, 1), model.deterministic, model.p, model.external)
        adjusted, meta = bias_adjust(draw, bias)
        branches[meta["branch"]] = branches.get(meta["branch"], 0) + 1
        responses.append(recursive(adjusted, policy, horizon)[0])
    return np.array(responses), {
        "generator": info,
        "outer_branches": branches,
        "bias_draws": bias_draws,
        "draws": draws,
        "resampling": "iid centered residual vectors",
        "bias_reuse": "same first-stage bias reused in second stage (Kilian step 2b)",
        "limitations": "pointwise, lag-conditional; nonstationary fits not forcibly stabilized",
    }


def cumulative_lp(
    model: Fit,
    policy: int,
    horizon: int,
    difference: bool,
    shock_column: int | None = None,
    scale: float = 1.0,
) -> tuple:
    column = policy if shock_column is None else shock_column
    _, impact, eps = recursive(model, column, 0)
    shock = eps[:, column] * impact[column, column]
    # Inflation dependent variables accumulated observation-by-observation before HAC,
    # rather than summing standard errors or assuming independent horizon estimates.
    y = model.y.copy()
    if difference:
        y[:, policy - 1] = np.cumsum(y[:, policy - 1])
    points, se, counts = lp_inputs(
        y, model.x, model.start, shock, column, horizon, hac=True, external=model.external
    )
    if difference:
        # Remove the pre-shock level; it is lag-measurable and in lagged inflation
        # controls only indirectly. Explicitly include that level as a nuisance control.
        lag = np.column_stack([model.x, y[model.start - 1 : -1, policy - 1]])
        points, se, counts = lp_inputs(
            y, lag, model.start, shock, column, horizon, hac=True, external=model.external
        )
    return points * scale, se * abs(scale), counts


def proxy_impact(model: Fit, instrument: np.ndarray, policy: int) -> tuple[np.ndarray, dict]:
    """Single-instrument residual covariance normalization and conventional first-stage F."""
    valid = np.isfinite(instrument)
    z = instrument[valid]
    u = model.resid[valid]
    if len(z) < 30 or np.std(z) < 1e-10:
        return np.full(model.y.shape[1], np.nan), {"status": "insufficient_instrument"}
    z = z - z.mean()
    v = u[:, policy] - u[:, policy].mean()
    b = float(z @ v / (z @ z))
    err = v - b * z
    se2 = float(err @ err) / (len(z) - 2) / float(z @ z)
    first_f = b * b / se2
    cov = z @ (u - u.mean(axis=0)) / len(z)
    if first_f <= 10 or abs(cov[policy]) < 1e-10:
        return np.full(u.shape[1], np.nan), {"status": "weak", "F": first_f, "nobs": len(z)}
    return cov / cov[policy], {
        "status": "identified_conditional",
        "F": first_f,
        "nobs": len(z),
        "strength_test": "conventional homoskedastic single-IV F",
        "exclusion_not_tested": True,
    }
