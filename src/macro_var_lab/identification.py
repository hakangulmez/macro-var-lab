"""Recursive-shock LPs and finite rotation sets; no puzzle-driven specification tuning."""

import numpy as np
from scipy.stats import norm  # type: ignore[import-untyped]

from macro_var_lab.var import Fit, ma, recursive


def projections(
    model: Fit, policy: int, horizon: int, min_df: int = 10, hac: bool = True
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    _, impact, eps = recursive(model, policy, 0)
    return lp_inputs(
        model.y,
        model.x,
        model.start,
        eps[:, policy] * impact[policy, policy],
        policy,
        horizon,
        min_df,
        hac,
        model.external,
    )


def lp_inputs(
    y: np.ndarray,
    lag_design: np.ndarray,
    start: int,
    shock: np.ndarray,
    policy: int,
    horizon: int,
    min_df: int = 10,
    hac: bool = True,
    external: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """LP on a supplied rate-unit shock; no VAR fit needed for a short regime."""
    controls = np.column_stack([lag_design, y[start:, :policy]])
    n, k = len(shock), y.shape[1]
    points = np.full((horizon + 1, k), np.nan)
    se = points.copy()
    counts = np.zeros(horizon + 1, dtype=int)
    for h in range(horizon + 1):
        count = n - h
        if count <= 0:
            continue
        x = controls[:count]
        z = shock[:count]
        target = y[start + h : start + h + count]
        rank = np.linalg.matrix_rank(x)
        if count - rank - 1 < min_df:
            continue
        z_res = z - x @ np.linalg.lstsq(x, z, rcond=None)[0]
        denominator = float(z_res @ z_res)
        if denominator < 1e-10:
            continue
        residualized = target - x @ np.linalg.lstsq(x, target, rcond=None)[0]
        b = (z_res @ residualized) / denominator
        points[h] = b
        counts[h] = count
        if hac:
            errors = residualized - z_res[:, None] * b
            score = z_res[:, None] * errors
            covariance = np.sum(score**2, axis=0)
            bandwidth = min(h + 1, count - 1)
            for lag in range(1, bandwidth + 1):
                covariance += (
                    2 * (1 - lag / (bandwidth + 1)) * np.sum(score[lag:] * score[:-lag], axis=0)
                )
            covariance *= count / (count - rank - 1)
            se[h] = np.sqrt(np.maximum(covariance, 0)) / denominator
        if external:
            points[h, :external] = 0
            se[h, :external] = 0
    return points, se, counts


def displayed(
    response: np.ndarray, columns: list[str], price_difference: bool, growth: bool = False
) -> np.ndarray:
    """Common price-level presentation, preserving inflation-native results separately."""
    result = response.copy()
    for j, name in enumerate(columns):
        if (name == "price" and price_difference) or (
            growth and name in ("activity", "fx", "brent", "vix")
        ):
            result[:, j] = np.cumsum(result[:, j], axis=0)
    return result


def rotations(
    model: Fit,
    policy: int,
    price: int,
    horizon: int,
    rng: np.random.Generator,
    draws: int,
    max_attempts: int,
    floor: float,
    price_difference: bool,
) -> tuple[np.ndarray, dict]:
    impact = np.linalg.cholesky(model.sigma)
    responses = ma(model, horizon) @ impact
    accepted: list[np.ndarray] = []
    weak = 0
    attempts = 0
    while len(accepted) < draws and attempts < max_attempts:
        attempts += 1
        q = np.zeros(len(impact))
        # Haar marginal of one orthogonal column; TR external components zero.
        q[model.external :] = rng.normal(size=len(impact) - model.external)
        q /= np.linalg.norm(q)
        candidate = responses @ q
        if candidate[0, policy] < 0:
            candidate = -candidate
        if candidate[0, policy] < floor * np.sqrt(model.sigma[policy, policy]):
            weak += 1
            continue
        price_path = np.cumsum(candidate[:, price]) if price_difference else candidate[:, price]
        if np.all(candidate[:4, policy] >= 0) and np.all(price_path[:4] <= 0):
            accepted.append(candidate / candidate[0, policy])
    if not accepted:
        return np.empty((0, horizon + 1, len(impact))), {
            "accepted": 0,
            "attempts": attempts,
            "weak_excluded": weak,
            "status": "empty_set",
        }
    return np.array(accepted), {
        "accepted": len(accepted),
        "attempts": attempts,
        "weak_excluded": weak,
        "status": "complete" if len(accepted) == draws else "incomplete",
        "not_confidence_intervals": True,
        "fixed_reduced_form": True,
        "median_not_necessarily_one_admissible_model": True,
    }


def hac_bands(point: np.ndarray, se: np.ndarray) -> dict[str, np.ndarray]:
    return {
        f"{side}{coverage}": point + direction * norm.ppf((1 + coverage / 100) / 2) * se
        for coverage in [68, 90]
        for side, direction in [("lo", -1), ("hi", 1)]
    }
