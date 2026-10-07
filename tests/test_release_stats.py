"""Statistical recovery, inference identities, stationarity branches and lag fallback."""

from dataclasses import replace

import numpy as np
import pytest

from macro_var_lab.release_stats import (
    bias_adjust,
    choose_lag,
    cumulative_lp,
    kilian_draws,
    proxy_impact,
    system_lm,
)
from macro_var_lab.var import fit


def fixture():
    rng = np.random.default_rng(52)
    y = np.zeros((200, 4))
    for t in range(1, 200):
        y[t] = 0.4 * y[t - 1] + rng.normal(size=4)
    return fit(y, np.ones((200, 1)), 1)


def test_correction_recovers_zero_bias_and_retains_external_masks():
    m = fixture()
    b, meta = bias_adjust(m, np.zeros_like(m.coefs))
    np.testing.assert_allclose(b.coefs, m.coefs)
    assert meta["weight"] == 1 and b.radius < 1
    # Deliberately explosive bias must shrink to a stationary corrected fit.
    b, meta = bias_adjust(m, -2 * np.ones_like(m.coefs))
    assert b.radius < 1 and 0 <= meta["weight"] < 1
    explosive = replace(m, coefs=m.coefs * 10)
    b, meta = bias_adjust(explosive, np.ones_like(m.coefs))
    assert b is explosive and meta["branch"] == "initially_nonstationary_unadjusted"
    a, info = kilian_draws(m, 2, 5, 5, 3, 5)
    assert a.shape == (5, 6, 4) and np.isfinite(a).all() and info["draws"] == 5
    np.testing.assert_allclose(a[:, 0, 2], 1)


def test_lag_and_lm_are_explicit_and_handle_unavailable_df():
    m = fixture()
    result = system_lm(m)
    assert 0 <= result["pvalue"] <= 1
    selected, ic, checks = choose_lag(m.y, m.deterministic, 4)
    assert selected.p >= min(ic, key=lambda r: r["BIC"])["lag"]
    selected, _, _ = choose_lag(m.y, m.deterministic, 4, force_bic=True)
    assert selected.p == min(ic, key=lambda r: r["BIC"])["lag"]
    assert system_lm(m, 190)["status"] == "insufficient_df"
    # Impossible maxlag offers explicit rank/df fallback rather than hiding failure.
    small = fixture().y[:45]
    selected, _, checks = choose_lag(small, np.ones((45, 1)), 12)
    assert selected.p >= 1 and checks


def test_proxy_recovers_known_impact_and_weak_gate():
    m = fixture()
    rng = np.random.default_rng(99)
    z = rng.normal(size=len(m.resid))
    u = rng.normal(scale=0.1, size=m.resid.shape) + z[:, None] * np.array([0, 0.2, 1, 0.4])
    strong = replace(m, resid=u)
    a, meta = proxy_impact(strong, z, 2)
    assert meta["F"] > 10 and a[2] == pytest.approx(1)
    assert a[3] == pytest.approx(0.4, abs=0.04)
    assert proxy_impact(m, np.zeros(len(z)), 2)[1]["status"] == "insufficient_instrument"
    weak = np.arange(len(z)) % 2
    assert proxy_impact(m, weak, 2)[1]["status"] == "weak"
    p, s, n = cumulative_lp(m, 2, 6, False)
    assert n[0] > 0 and p.shape == s.shape == (7, 4)
    p, s, n = cumulative_lp(m, 2, 6, True, shock_column=3, scale=10)
    assert np.isfinite(p).all() and np.all(s >= 0)


def test_release_synthetic_resume_and_declared_robustness(tmp_path):
    import json
    from pathlib import Path

    import pandas as pd
    import yaml

    from macro_var_lab.release import run

    repo = Path(__file__).parents[1]
    config = yaml.safe_load((repo / "configs/g2.yaml").read_text())
    (tmp_path / "configs").mkdir()
    (tmp_path / "data/processed").mkdir(parents=True)
    (tmp_path / "configs/g2.yaml").write_text(yaml.safe_dump(config))
    index = pd.period_range("1998-12", "2026-09", freq="M")
    columns = [
        "brent",
        "vix",
        "fedfunds",
        "ea_ip",
        "ea_hicp",
        "ea_2y",
        "eurusd",
        "tr_ip",
        "tr_cpi",
        "tr_aofm",
        "usdtry",
        "tr_reer",
    ]
    rng = np.random.default_rng(72)
    y = rng.normal(size=(len(index), len(columns)))
    for t in range(1, len(y)):
        y[t] += 0.2 * y[t - 1]
    pd.DataFrame(y + 100, index=index, columns=columns).to_csv(
        tmp_path / "data/processed/baseline_levels.csv"
    )
    summary = run(tmp_path, quick=True)
    again = run(tmp_path, quick=True)
    assert summary["analysis_id"] == again["analysis_id"] and summary["paid_calls"] == 0
    assert set(summary["models"]) == {
        "EA_baseline",
        "TR_baseline",
        "EA_BIC",
        "TR_BIC",
        "TR_FX_first",
        "TR_easing_dummy",
    }
    assert summary["proxy"]["status"] == "skipped_quick"
    rows = pd.read_csv(tmp_path / "results/g3_irfs.csv")
    assert "TR_pass_through" in set(rows.model)
    assert "sign_set" in set(rows.method)
    assert json.loads((tmp_path / "results/g3_summary.json").read_text())["paid_calls"] == 0
