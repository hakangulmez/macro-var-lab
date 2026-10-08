import numpy as np

from macro_var_lab.var import fit, residual_checks


def test_policy_granger_invariant_to_consistent_column_reordering():
    rng = np.random.default_rng(20261007)
    y = np.zeros((350, 6))
    innovations = rng.normal(size=y.shape)
    for t in range(2, len(y)):
        y[t] = 0.25 * y[t - 1] + innovations[t]
        y[t, 3] += 0.7 * y[t - 1, 4]
    labels = ["brent", "vix", "activity", "price", "policy", "fx"]
    d = np.ones((len(y), 1))
    baseline = residual_checks(fit(y, d, 2), labels)
    for order in [[0, 1, 2, 3, 5, 4], [4, 0, 5, 3, 1, 2]]:
        names = [labels[j] for j in order]
        result = residual_checks(fit(y[:, order], d, 2), names)
        assert result["granger_tested_variable"] == "policy"
        assert result["granger_policy_column"] == names.index("policy")
        for name in labels:
            np.testing.assert_allclose(
                result["granger_policy_to"][name]["statistic"],
                baseline["granger_policy_to"][name]["statistic"],
                rtol=1e-10,
                atol=1e-10,
            )
            np.testing.assert_allclose(
                result["granger_policy_to"][name]["pvalue"],
                baseline["granger_policy_to"][name]["pvalue"],
                rtol=1e-10,
                atol=1e-10,
            )


def test_unlabelled_generic_system_does_not_guess_a_policy_variable():
    y = np.random.default_rng(2).normal(size=(80, 4))
    result = residual_checks(fit(y, np.ones((80, 1)), 1), list("abcd"))
    assert result["granger_status"] == "not_tested_no_policy_label"
    assert result["granger_policy_to"] == {}


def test_common_sample_p3_p7_and_bootstrap_keep_explicit_presample():
    import pandas as pd

    from macro_var_lab.release_stats import kilian_draws
    from macro_var_lab.v3_comparison import required_panel

    index = pd.period_range("2004-09", "2025-10", freq="M")
    frame = pd.DataFrame(
        np.ones((len(index), 6)),
        index=index,
        columns=["brent", "vix", "ea_ip", "ea_hicp", "ea_2y", "eurusd"],
    )
    _, missing = required_panel(frame, "2004-09")
    assert len(missing["ea_2y"]) == 7
    panel, missing = required_panel(frame, "2005-04")
    assert not missing
    y = np.random.default_rng(5).normal(size=(len(panel), 6))
    d = np.ones((len(panel), 1))
    for p in [3, 7]:
        model = fit(y, d, p, start=7)
        assert len(model.resid) == 247 and str(panel.index[model.start]) == "2005-04"
        draws, meta = kilian_draws(model, 4, 2, seed=23, bias_draws=2, draws=3)
        assert draws.shape == (3, 3, 6) and meta["draws"] == 3
