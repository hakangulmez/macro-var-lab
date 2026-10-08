# ruff: noqa: E501
"""Presentation-only formatting of empirical aggregate outputs."""


def generate(csv, js, macro, table, fmt):
    s = js("g3_summary.json")
    g1 = js("g1_data_checks.json")
    g2 = js("g2_summary.json")
    f = csv("g3_irfs.csv")
    cfg = s["contract"]["config"]
    for key, field in [
        ("Horizon", "horizon"),
        ("OuterDraws", "bootstrap_draws"),
        ("BiasDraws", "bias_draws"),
        ("BlockLength", "bootstrap_block"),
        ("SignDraws", "sign_draws"),
        ("RateFloor", "sign_rate_floor_sd"),
        ("LagCap", "lag_max"),
        ("Seed", "seed"),
    ]:
        macro(key, cfg[field])
    for prefix, name in [("EA", "EA_baseline"), ("TR", "TR_baseline")]:
        r = s["models"][name]
        macro(prefix + "Lag", r["lag"])
        macro(prefix + "Start", r["spec"]["start"])
        macro(prefix + "End", r["spec"]["end"])
        macro(prefix + "Radius", r["radius"], 5)
    proxy = s["proxy"]
    macro("ProxyF", proxy["F"], 3)
    macro("ProxyN", proxy["nobs"])
    macro("ProxyDraws", proxy["bootstrap_successful"])
    macro("ProxyStart", proxy["sample"][0])
    macro("ProxyEnd", proxy["sample"][1])
    macro("ProxyLag", proxy["LM_search"][-1]["lag"])
    macro("TRLevelsRadius", s["TR_transform"]["levels_radius"], 5)
    macro(
        "MissingEarlyHICP",
        len(
            [
                m
                for m in g1["series"]["ea_hicp"]["coverage"]["missing_dates"]
                if m.startswith("1999-")
            ]
        ),
    )
    for prefix, model, method, var in [
        ("ProxyFX", "EA_proxy_overlap", "proxy", "fx"),
        ("ProxyPrice", "EA_proxy_overlap", "proxy", "price"),
        ("ProxyIP", "EA_proxy_overlap", "proxy", "activity"),
        ("TRPrice", "TR_baseline", "recursive", "price"),
    ]:
        row = f.query("model==@model and method==@method and variable==@var and horizon==12").iloc[
            0
        ]
        for suffix, col in [("Point", "estimate"), ("Low", "lo90"), ("High", "hi90")]:
            macro(prefix + suffix, row[col], 3)
    groups = [
        (
            "data_main",
            [
                "ea_ip",
                "ea_hicp",
                "ea_2y",
                "eurusd",
                "brent",
                "vix",
                "tr_ip",
                "tr_cpi",
                "tr_aofm",
                "usdtry",
                "fedfunds",
            ],
        ),
        (
            "data_alternatives",
            [
                "ea_core",
                "ea_eonia",
                "ea_estr",
                "de_2y",
                "tr_core_b",
                "tr_core_c",
                "tr_reer",
                "tr_cpi_old",
                "tr_core_b_old",
                "tr_core_c_old",
            ],
        ),
    ]
    for name, keys in groups:
        rows = []
        for key in keys:
            if key not in g1["series"]:
                continue
            r = g1["series"][key]
            sp = r["spec"]
            co = r["coverage"]
            identifier = sp["identifier"]
            selectors = sp.get("selectors", {})
            identity = sp["provider"] + ": " + identifier
            if selectors:
                identity += "; " + ", ".join(
                    str(v) for k, v in selectors.items() if k not in ["freq"]
                )
            transforms = {"log100": "100 log(level)", "log": "log(level)", "rate": "pp levels"}
            rows.append(
                [
                    key,
                    identity,
                    transforms.get(sp["transform"], sp["transform"]),
                    co["first_observed"] + " to " + co["last_observed"],
                ]
            )
        if name == "data_alternatives":
            co = g1["series"]["tr_announced"]["coverage"]
            rows.append(
                [
                    "tr_announced",
                    "CBRT public effective-date O/N borrowing and one-week repo lending tables",
                    "pp; daily step mean",
                    co["first_observed"] + " to " + co["last_observed"],
                ]
            )
        table(
            name,
            ["Variable", "Source / exact ID and selectors", "Transformation", "Observed coverage"],
            rows,
            "Series definitions: "
            + ("baseline inputs" if name == "data_main" else "declared alternatives"),
            (
                "Source: author's calculations from the documented inputs. "
                "Coverage is source availability, not a"
                " common estimation sample. Daily series use observed monthly means before "
                "transformation. Missing months remain missing."
            ),
            layout="p{0.12\\linewidth}p{0.40\\linewidth}p{0.17\\linewidth}p{0.21\\linewidth}",
            size="footnotesize",
        )
    comparison = csv("v3_methods_comparison.csv")
    vm = js("v3_methods_manifest.json")
    for prefix, lag in [("PThree", 3), ("PSeven", 7)]:
        macro(prefix + "F", vm["panels"][str(lag)]["proxy"]["F"], 3)
        macro(prefix + "Draws", vm["panels"][str(lag)]["proxy"]["successful_draws"])
        for variable, label in [("fx", "FX"), ("price", "Price"), ("activity", "IP")]:
            a = comparison[
                (comparison.lag == lag)
                & (comparison.method == "proxy VAR")
                & (comparison.variable == variable)
            ].iloc[0]
            for suffix, col in [("Point", "estimate"), ("Low", "lo90"), ("High", "hi90")]:
                macro(prefix + label + suffix, a[col], 3)
    macro("ComparisonN", vm["panels"]["3"]["nobs"])
    macro("ComparisonStart", vm["panels"]["3"]["usable_sample"][0])
    macro("ComparisonEnd", vm["panels"]["3"]["usable_sample"][1])
    rows = []
    for _, a in comparison.iterrows():
        sign = a.method == "sign-restricted VAR"
        rows.append(
            [
                int(a.lag),
                a.method,
                a.variable,
                fmt(a.estimate),
                fmt(a["min"] if sign else a.lo90),
                fmt(a["max"] if sign else a.hi90),
                "range" if sign else "90%",
            ]
        )
    table(
        "ea_results",
        ["p", "Method", "Outcome", "Response", "Lower", "Upper", "Type"],
        rows,
        "Methods comparison on a common sample and lag specification, month twelve",
        "Source: author calculations. April 2005–October 2025; 247 usable VAR observations at each lag. Identical variables/transforms/deterministics and 100 bp normalization. Recursive-shock LP changes response estimator, not its shock identification; 235 supported origins at horizon 12. Sign ranges are not statistical intervals. Proxy inference is conditional, F3="
        + fmt(vm["panels"]["3"]["proxy"]["F"])
        + ", F7="
        + fmt(vm["panels"]["7"]["proxy"]["F"])
        + "; neither lag selected for significance.",
        layout="rXlrrrl",
        size="footnotesize",
    )
    tr = f[
        (f["model"].isin(["TR_baseline", "TR_FX_first"]))
        & f["method"].isin(["recursive", "LP_HAC"])
        & f["variable"].isin(["price", "activity", "fx"])
        & (f.horizon == 12)
    ]
    rows = [
        [
            ("FX first" if r["model"] == "TR_FX_first" else r["method"].replace("_", " ")),
            r.variable,
            fmt(r.estimate),
            fmt(r.lo90),
            fmt(r.hi90),
        ]
        for _, r in tr.iterrows()
    ]
    table(
        "tr_results",
        ["Method", "Outcome", "Response", "Lower 90%", "Upper 90%"],
        rows,
        "Türkiye responses at the headline horizon",
        (
            "Source: monetary-response aggregates, horizon 12. Price responses accumulate monthly"
            " inflation; exchange-rate increases mean depreciation."
        ),
        layout="Xlrrr",
    )
    fe = csv("g3_fevd.csv")
    fe = fe[
        fe.model.isin(["EA_baseline", "TR_baseline"])
        & fe.variable.isin(["price", "activity", "fx"])
        & (fe.horizon == 12)
    ]
    table(
        "fevd",
        ["Area", "Outcome", "Share", "Lower 90%", "Upper 90%"],
        [
            [r.model[:2], r.variable, fmt(r.policy_share), fmt(r.lo90), fmt(r.hi90)]
            for _, r in fe.iterrows()
        ],
        "Recursive policy-shock forecast-error variance shares",
        (
            "Recursive Cholesky; EA usable "
            + fe[fe.model == "EA_baseline"].sample_start.iloc[0]
            + "–"
            + fe[fe.model == "EA_baseline"].sample_end.iloc[0]
            + ", p="
            + str(int(fe[fe.model == "EA_baseline"].lag.iloc[0]))
            + "; TR usable "
            + fe[fe.model == "TR_baseline"].sample_start.iloc[0]
            + "–"
            + fe[fe.model == "TR_baseline"].sample_end.iloc[0]
            + ", p="
            + str(int(fe[fe.model == "TR_baseline"].lag.iloc[0]))
            + ". Horizon12; fractions, not "
            "percentages; EA price level and TR inflation-native FEVD are different "
            "outcomes."
        ),
        layout="Xlrrr",
    )
    hd = csv("g3_history_annual.csv")
    hd = hd[hd.year.isin([2020, 2022, 2025, 2026])]
    table(
        "history",
        ["Area", "Year", "Months", "Monthly infl.", "Policy part", "Lower90%", "Upper90%"],
        [
            [
                r.model[:2],
                str(int(r.year)) + (" partial" if r.partial_year else ""),
                int(r.contributing_months),
                fmt(r.mean_inflation),
                fmt(r.mean_policy_contribution),
                fmt(r.lo90),
                fmt(r.hi90),
            ]
            for _, r in hd.iterrows()
        ],
        "Recursive Cholesky: annual averages of monthly log inflation and policy contributions",
        (
            "EA usable "
            + hd[hd.model == "EA_baseline"].sample_start.iloc[0]
            + "–"
            + hd[hd.model == "EA_baseline"].sample_end.iloc[0]
            + ", p="
            + str(int(hd[hd.model == "EA_baseline"].lag.iloc[0]))
            + "; TR usable "
            + hd[hd.model == "TR_baseline"].sample_start.iloc[0]
            + "–"
            + hd[hd.model == "TR_baseline"].sample_end.iloc[0]
            + ", p="
            + str(int(hd[hd.model == "TR_baseline"].lag.iloc[0]))
            + ". Units: percentage points of monthly100delta(log P), arithmetic annual mean, NOT annual inflation.2026: January–July,7 months, no annualisation. Partial first/final years are not "
            "full-year averages. Bands apply to policy contributions; "
            "deterministic/initial history and all other shocks complete the identity."
        ),
        layout="Xrrrrrr",
        size="footnotesize",
    )
    rows = []
    for name, r in s["models"].items():
        if "spec" not in r or r["spec"]["kind"] == "baseline" and name.endswith("baseline"):
            continue
        sp = r["spec"]
        q = f[
            (f.model == name)
            & (f.method == "recursive")
            & (f.variable == "price")
            & (f.horizon == 12)
        ]
        if q.empty:
            continue
        a = q.iloc[0]
        rows.append(
            [
                name.replace("_", " "),
                sp["start"] + " / " + sp["end"],
                r["lag"],
                fmt(a.estimate),
                f"[{fmt(a.lo90)}, {fmt(a.hi90)}]",
            ]
        )
    checkpoint = csv("g2_irfs.csv")
    extra = [
        ("EA LP", "EA_baseline", "LP_HAC"),
        ("TR LP", "TR_baseline", "LP_HAC"),
        ("EA sign set", "EA_baseline", "sign_set"),
        ("TR sign set", "TR_baseline", "sign_set"),
        ("EA event proxy", "EA_proxy_overlap", "proxy"),
        ("EA ordinary block", "EA_baseline", "plain_block"),
        ("TR ordinary block", "TR_baseline", "plain_block"),
        ("FX pass-through", "TR_pass_through", "LP_HAC"),
        ("Recent TR LP, native", "TR_recent_LP_native", "LP_HAC"),
    ]
    for label, model, method in extra:
        part = f[
            (f.model == model) & (f.method == method) & (f.variable == "price") & (f.horizon == 12)
        ]
        if part.empty:
            rows.append([label, "Reported horizons", "--", "--", "unavailable"])
        else:
            a = part.iloc[0]
            sign = method == "sign_set"
            lo = a["min"] if sign else a.lo90
            hi = a["max"] if sign else a.hi90
            rows.append(
                [
                    label,
                    "See method sample",
                    "--",
                    fmt(a.estimate),
                    ("range " if sign else "") + f"[{fmt(lo)}, {fmt(hi)}]",
                ]
            )
    for name, label in [
        ("TR_regime_1", "Early TR regime"),
        ("TR_regime_2", "Middle TR regime"),
    ]:
        r = g2["models"][name]
        a = checkpoint[
            (checkpoint.model == name)
            & (checkpoint.method == "recursive")
            & (checkpoint.variable == "price")
            & (checkpoint.horizon == 12)
        ].iloc[0]
        rows.append(
            [
                label,
                r["spec"]["start"] + " / " + r["spec"]["end"],
                r["lag"],
                fmt(a.estimate),
                f"[{fmt(a.lo90)}, {fmt(a.hi90)}]",
            ]
        )
    rows.extend(
        [
            [
                "Johansen/VECM",
                "Integration conditions",
                "--",
                "--",
                g2["vecm"]["status"].replace("_", " "),
            ],
            ["TR bond-yield indicators", "Official source unavailable", "--", "--", "not included"],
            ["Old-base core splice", "Bridge tolerance", "--", "--", "rejected"],
        ]
    )
    table(
        "robustness",
        ["Declared alternative", "Sample", "Lag", "Price", "90% interval"],
        rows,
        "Specifications and alternative estimates",
        (
            "Sources: monetary-response aggregates and earlier regime "
            "tables. Responses at horizon 12; sign endpoints are ranges. Recent LP "
            "reports native inflation; pass-through scales the FX innovation, not the "
            "policy shock. Rejected/unestimated alternatives have no fabricated "
            "numerical result."
        ),
        layout="p{0.29\\linewidth}p{0.23\\linewidth}rrX",
        size="footnotesize",
    )
    rows = []
    for name in ["EA_baseline", "TR_baseline"]:
        for r in s["models"][name]["lag_IC"]:
            rows.append(
                [name[:2], r["lag"], r["nobs_common"], fmt(r["AIC"]), fmt(r["BIC"]), fmt(r["HQ"])]
            )
    table(
        "lags",
        ["Area", "Lag", "Common n", "AIC", "BIC", "HQ"],
        rows,
        "Common-window information criteria before the residual screen",
        (
            "Source: lag-selection aggregates. Our final lag selection adds the "
            "equation-BG residual screen; BIC-only diagnostics are reported separately."
        ),
        layout="Xrrrrr",
        size="footnotesize",
    )
    u = csv("g2_unit_roots.csv")
    u = u[(u.variable == "tr_cpi") & u.test.isin(["ADF_c", "PP_c", "KPSS_c", "ZA_ct"])]
    table(
        "roots",
        ["Sample", "Transform", "Test", "Statistic", "p value", "Lag"],
        [
            [
                r["sample"],
                r["transform"],
                r["test"].replace("_", " "),
                fmt(r.statistic),
                fmt(r.pvalue),
                int(r.lags),
            ]
            for _, r in u.iterrows()
        ],
        "Saved log-CPI and first-difference integration diagnostics",
        (
            "Source: author's calculations from the documented inputs. "
            "ADF/PP null: unit root; KPSS null: "
            "stationarity. Reported KPSS endpoint p values are bounds from lookup "
            "tables. ZA allows one endogenous break."
        ),
        layout="p{0.26\\linewidth}lXrrr",
        size="footnotesize",
    )
    rows = []
    for name in ["EA_baseline", "TR_baseline"]:
        r = s["models"][name]
        for var in r["variables"]:
            diag = r["diagnostics"]
            bg = diag["BG_LM"][var]
            rows.append(
                [
                    name[:2],
                    var,
                    fmt(bg["1"].get("pvalue")),
                    fmt(bg["6"].get("pvalue")),
                    fmt(bg["12"].get("pvalue")),
                    fmt(diag["JB_marginal"][var]["pvalue"]),
                ]
            )
    table(
        "residuals",
        ["Area", "Equation", "BG(1) p", "BG(6) p", "BG(12) p", "JB p"],
        rows,
        "Marginal residual diagnostics at the selected lag",
        (
            "Source: author's calculations from the documented inputs. "
            "Unavailable tests are dashes. These are "
            "equation tests, not an omnibus system LR test; normality failures motivate "
            "transparent bootstrap qualifications."
        ),
        layout="Xlrrrr",
        size="footnotesize",
    )
    rows = []
    for name in ["EA_baseline", "TR_baseline"]:
        r = s["models"][name]
        b = r["plain_bootstrap"]
        sg = r["signs"]
        rows.append(
            [
                name[:2],
                fmt(r["radius"], 5),
                b["successful"],
                b["unstable_retained"],
                sg["accepted"],
                sg["attempts"],
                f"{r['history_reconstruction_error']:.2e}",
            ]
        )
    table(
        "computation",
        ["Area", "Radius", "Block ok", "Unstable", "Signs", "Attempts", "HD error"],
        rows,
        "Saved computation and accounting diagnostics",
        (
            "Source: author's calculations from the documented inputs. "
            "Block ok counts successful ordinary block "
            "resamples, not Kilian corrections. HD error is the maximum absolute "
            "reconstruction error."
        ),
        layout="Xrrrrrr",
        size="footnotesize",
    )
    bridge = js("price_bridge_detail.json")
    table(
        "bridge",
        ["Index", "Overlap", "Growth gap pp", "Ratio range %", "Tolerance %"],
        [
            [
                k,
                v["overlap_start"] + " / " + v["overlap_end"],
                fmt(v["max_abs_monthly_log_growth_gap_pp"], 6),
                fmt(100 * g1["price_bridge_checks"][k]["ratio_relative_range"], 6),
                fmt(100 * g1["price_bridge_checks"][k]["tolerance"], 3),
            ]
            for k, v in bridge.items()
        ],
        "Price-rebasing bridge diagnostics",
        (
            "Source: author's calculations from the documented inputs. "
            "Current series already cover the "
            "analysis window. No core-index splice is used."
        ),
        layout="Xp{0.26\\linewidth}rrr",
        size="footnotesize",
    )
    macro("VecmStatus", g2["vecm"]["status"].replace("_", " "))

    from pathlib import Path

    import pandas as pd

    generated = Path(__file__).resolve().parent / "generated"
    for name, source, keys in [
        ("fevd", fe, ["model", "variable"]),
        ("history", hd, ["model", "year"]),
    ]:
        export = pd.read_csv(generated / (name + ".csv"))
        export["identification"] = "recursive Cholesky"
        for key in ["sample_start", "sample_end", "lag", "units"]:
            export[key] = source[key].to_numpy()
        if name == "history":
            for key in [
                "contributing_months",
                "coverage_start",
                "coverage_end",
                "partial_year",
                "aggregation",
            ]:
                export[key] = source[key].to_numpy()
        export.to_csv(generated / (name + ".csv"), index=False)
