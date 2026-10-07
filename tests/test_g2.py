"""Analytic, library cross-check and synthetic recovery tests; no empirical/network input."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from statsmodels.tsa.api import VAR

from macro_var_lab import var
from macro_var_lab.g2 import bootstrap, prepare, recent_lp, run, vecm_pass
from macro_var_lab.identification import displayed, hac_bands, lp_inputs, projections, rotations


def sample(n=200, k=4):
    rng = np.random.default_rng(20261007)
    y = np.zeros((n, k))
    a = np.diag(np.linspace(0.2, 0.65, k))
    a[-1, -2] = 0.2
    for t in range(1, n):
        y[t] = a @ y[t - 1] + rng.normal(size=k)
    return y, np.ones((n, 1))


def test_var_matches_statsmodels_and_analytic_impulse_paths():
    y, d = sample()
    m = var.fit(y, d, 2)
    standard = VAR(y, exog=d).fit(2, trend="n")
    np.testing.assert_allclose(m.coefs, standard.coefs, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(m.resid, standard.resid, atol=1e-10)
    np.testing.assert_allclose(m.sigma, standard.sigma_u_mle, atol=1e-10)
    np.testing.assert_allclose(var.ma(m, 12), standard.ma_rep(12), atol=1e-10)
    assert m.radius < 1
    r, p, eps = var.recursive(m, 2, 36)
    assert r[0, 2] == pytest.approx(1)
    np.testing.assert_allclose(r[0, :2], 0, atol=1e-12)
    np.testing.assert_allclose(eps @ p.T, m.resid, atol=1e-12)
    assert np.allclose(var.fevd(m, 36).sum(axis=2), 1)
    base, effects, error = var.history(m)
    assert error < 1e-10
    np.testing.assert_allclose(base + effects.sum(axis=2), y, atol=1e-10)
    fitted, ic = var.select(y, d, 6)
    assert {row["nobs_common"] for row in ic} == {len(y) - 6}
    assert fitted.p == min(ic, key=lambda row: row["BIC"])["lag"]
    index = pd.period_range("2018-01", periods=len(y), freq="M")
    det = var.deterministic(index, True)
    assert det.shape == (len(y), 13) and det[0, -1] == 0 and det[-1, -1] == 1
    shocks1 = var.simulate(m, np.random.default_rng(4))
    shocks2 = var.simulate(m, np.random.default_rng(4))
    np.testing.assert_array_equal(shocks1, shocks2)
    np.testing.assert_array_equal(shocks1[:2], y[:2])


def test_external_block_enforces_dynamic_and_contemporaneous_zero_effects():
    y, d = sample(n=240, k=7)
    m = var.fit(y, d, 2, 3)
    assert np.all(m.coefs[:, :3, 3:] == 0)
    response, _, _ = var.recursive(m, 5, 36)
    np.testing.assert_allclose(response[:, :3], 0, atol=1e-12)
    diag = var.residual_checks(m, ["brent", "vix", "fedfunds", "activity", "price", "policy", "fx"])
    assert diag["granger_policy_to"]["brent"]["status"] == "excluded_by_design"
    assert diag["BG_LM"]["price"]["1"]["pvalue"] >= 0
    small, ds = sample(n=40, k=4)
    diag = var.residual_checks(var.fit(small, ds, 1), list("abcd"))
    assert diag["BG_LM"]["a"]["12"]["status"] == "insufficient_df_or_rank"
    with pytest.raises(ValueError, match="Finite"):
        var.fit(y * np.nan, d, 2)
    with pytest.raises(ValueError, match="alignment"):
        var.fit(y, d, 2, start=1)
    with pytest.raises(ValueError, match="degrees"):
        var.fit(y, np.column_stack([d, d]), 2)
    duplicate = y.copy()
    duplicate[:, 1] = duplicate[:, 0]
    with pytest.raises(ValueError):
        var.fit(duplicate, d, 2)
    weak = replace(m, sigma=np.eye(7) * 1e-24)
    with pytest.raises(ValueError, match="Weak"):
        var.recursive(weak, 5, 4)


def test_lp_hac_matches_statsmodels_and_cholesky_impact():
    y, d = sample(n=240, k=4)
    m = var.fit(y, d, 2)
    points, se, counts = projections(m, 2, 6)
    _, p, eps = var.recursive(m, 2, 0)
    control = np.column_stack([m.x, m.y[m.start :, :2]])
    shock = eps[:, 2] * p[2, 2]
    for h in [0, 3, 6]:
        n = len(shock) - h
        x = np.column_stack([control[:n], shock[:n]])
        estimated = sm.OLS(y[m.start + h : m.start + h + n, 3], x).fit(
            cov_type="HAC", cov_kwds={"maxlags": h + 1, "use_correction": True}
        )
        assert points[h, 3] == pytest.approx(estimated.params[-1], abs=1e-10)
        assert se[h, 3] == pytest.approx(estimated.bse[-1], rel=1e-9)
    np.testing.assert_allclose(points[0], var.recursive(m, 2, 0)[0][0], atol=1e-10)
    bands = hac_bands(points, se)
    assert np.all(bands["hi90"] >= bands["hi68"])
    blocked = var.fit(y, d, 1, external=1)
    lp, sd, _ = projections(blocked, 2, 3)
    assert np.all(lp[:, 0] == 0) and np.all(sd[:, 0] == 0)
    lp, _, counts = lp_inputs(y, m.x, m.start, np.zeros(len(m.resid)), 2, 250)
    assert counts.sum() == 0 and np.isnan(lp).all()
    assert projections(m, 2, 6, min_df=1000)[2].sum() == 0
    short = recent_lp(
        var.fit(sample(200, 7)[0], np.ones((200, 1)), 1, 3),
        160,
        {"horizon": 36, "min_lp_residual_df": 10},
    )
    assert short[0].shape == (37, 4) and short[2][-1] == 0


def test_sign_set_conditions_and_price_cumulation_are_explicit():
    y, d = sample()
    m = var.fit(y, d, 1)
    for inflation in [False, True]:
        draws, info = rotations(m, 2, 1, 12, np.random.default_rng(12), 30, 10000, 0.1, inflation)
        assert len(draws) == 30 and info["not_confidence_intervals"]
        assert np.all(draws[:, :4, 2] >= 0)
        prices = np.cumsum(draws[:, :, 1], axis=1) if inflation else draws[:, :, 1]
        assert np.all(prices[:, :4] <= 0)
        np.testing.assert_allclose(draws[:, 0, 2], 1)
    empty, info = rotations(m, 2, 1, 4, np.random.default_rng(1), 2, 2, 100, False)
    assert not len(empty) and info["weak_excluded"] == 2
    incomplete, info = rotations(m, 2, 1, 4, np.random.default_rng(1), 100, 10, 0.1, False)
    assert info["status"] == "incomplete"
    r = np.ones((4, 4))
    shown = displayed(r, ["activity", "price", "policy", "fx"], True, True)
    np.testing.assert_array_equal(shown[:, 1], [1, 2, 3, 4])
    np.testing.assert_array_equal(shown[:, 2], 1)
    np.testing.assert_array_equal(r, 1)


def test_bootstrap_resume_matches_fresh_run_and_reconstructs_actual_history(tmp_path):
    y, d = sample(n=140)
    m = var.fit(y, d, 1)
    labels = ["activity", "price", "policy", "fx"]
    c = {
        "bootstrap_draws": 3,
        "horizon": 6,
        "seed": 20261007,
        "bootstrap_block": 6,
        "min_lp_residual_df": 10,
    }
    a, meta = bootstrap(m, labels, 2, c, tmp_path / "resume.npz", 8, False, False, True)
    c["bootstrap_draws"] = 6
    b, meta = bootstrap(m, labels, 2, c, tmp_path / "resume.npz", 8, False, False, True)
    fresh, _ = bootstrap(m, labels, 2, c, tmp_path / "fresh.npz", 8, False, False, True)
    assert meta["successful"] == 6
    for key in ["var", "lp", "fevd", "history"]:
        np.testing.assert_array_equal(b[key], fresh[key])
    np.testing.assert_array_equal(a["var"], b["var"][:3])


def test_vecm_is_conditionally_skipped_and_recovers_known_cointegration():
    rng = np.random.default_rng(17)
    index = pd.period_range("2005-01", "2026-07", freq="M")
    x = np.cumsum(rng.normal(size=len(index)))
    z = np.cumsum(rng.normal(size=len(index)))
    frame = pd.DataFrame(
        {"tr_cpi": x, "usdtry": x + rng.normal(scale=0.1, size=len(x)), "tr_reer": z}, index=index
    )
    gates = {name: {"I1_established_by_agreement_rule": False} for name in frame}
    assert vecm_pass(frame, gates)["status"] == "not_estimated"
    gates = {name: {"I1_established_by_agreement_rule": True} for name in frame}
    result = vecm_pass(frame, gates)
    assert result["status"] == "estimated" and result["rank_95"] == 1


def test_complete_synthetic_g2_has_no_network_or_empirical_reads(tmp_path, monkeypatch):
    import json
    import subprocess

    import requests
    import yaml

    root = Path(__file__).parents[1]
    (tmp_path / "data/processed").mkdir(parents=True)
    (tmp_path / "results").mkdir()
    index = pd.period_range("1998-12", "2026-09", freq="M")
    rng = np.random.default_rng(20261007)
    original = yaml.safe_load((root / "configs/data.yaml").read_text())
    columns = [s["name"] for s in original["series"]] + [
        "tr_announced",
        "ea_overnight",
        "ea_overnight_adjusted",
    ]
    y = rng.normal(size=(len(index), len(columns)))
    for t in range(1, len(y)):
        y[t] += 0.5 * y[t - 1]
    frame = pd.DataFrame(y + 100, index=index, columns=columns)
    frame.to_csv(tmp_path / "data/processed/baseline_levels.csv")
    (tmp_path / "results/g1_data_checks.json").write_text(
        json.dumps({"status": "data_checked", "run": "synthetic"})
    )
    config = yaml.safe_load((root / "configs/g2.yaml").read_text())
    config.update(bootstrap_draws=3, sign_draws=10, horizon=6)
    path = tmp_path / "g2.yaml"
    path.write_text(yaml.safe_dump(config))
    monkeypatch.setattr(
        subprocess, "check_output", lambda *a, **kw: "fixture-commit\n" if kw.get("text") else b""
    )
    monkeypatch.setattr(requests, "get", lambda *a, **kw: pytest.fail("G2 must be offline"))
    result = run(tmp_path, path)
    assert result["paid_calls"] == 0 and result["models"]["TR_regime_3_LP"]["no_VAR_estimated"]
    assert len(result["models"]) == 15
    short_rows = pd.read_csv(tmp_path / "results/g2_irfs.csv")
    short_impact = short_rows.query(
        "model == 'TR_regime_3_LP' and variable == 'policy' and horizon == 0"
    )
    np.testing.assert_allclose(short_impact.estimate, 1, atol=1e-9)
    assert (tmp_path / "results/g2_fevd.csv").exists()
    spec = config["models"][0]
    frame.iloc[150, 0] = np.nan
    with pytest.raises(ValueError, match="missing"):
        prepare(frame, spec, False)
