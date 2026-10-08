# ruff: noqa: E501
"""Render external-facing summaries from saved aggregates, without estimation."""

import hashlib
import json
from pathlib import Path

import pandas as pd
from policy import write_note

root = Path(__file__).resolve().parents[1]
name = root.name
res = root / "results"
inputs = {}


def csv(filename):
    path = res / filename
    inputs[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pd.read_csv(path)


if name == "macro-var-lab":
    v = csv("v3_methods_comparison.csv")
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image

    table = csv("v3_methods_irfs.csv")
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), sharex=True)
    for i, lag in enumerate([3, 7]):
        for j, variable in enumerate(["price", "activity", "fx"]):
            ax = axes[i, j]
            for method, color in zip(
                ["recursive VAR", "recursive-shock LP", "sign-restricted VAR", "proxy VAR"],
                ["#0072B2", "#009E73", "#E69F00", "#D55E00"],
                strict=True,
            ):
                part = table[
                    (table.lag == lag) & (table.variable == variable) & (table.method == method)
                ].sort_values("horizon")
                ax.plot(part.horizon, part.estimate, label=method, color=color, lw=1.3)
                if method.startswith("sign"):
                    ax.plot(part.horizon, part["min"], ls="--", lw=0.6, color=color)
                    ax.plot(part.horizon, part["max"], ls="--", lw=0.6, color=color)
                else:
                    ax.fill_between(part.horizon, part.lo90, part.hi90, color=color, alpha=0.15)
            ax.axhline(0, color=".4", lw=0.5)
            ax.set(title=f"p = {lag}: {variable}", xlabel="Months", ylabel="100 log response")
            limits = table[
                (table.lag == lag)
                & (table.variable == variable)
                & (~table.method.str.startswith("sign"))
            ][["lo90", "hi90"]].to_numpy()
            lo, hi = np.nanmin(limits), np.nanmax(limits)
            pad = 0.1 * (hi - lo)
            ax.set_ylim(lo - pad, hi + pad)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=9)
    fig.suptitle(
        "Methods comparison on a common sample and lag specification\nApril 2005-October 2025; identical usable VAR dates within both panels"
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.93))
    fig.savefig(root / "figures/v3_methods_comparison.png", dpi=250)
    fig.savefig(root / "figures/headline.png", dpi=250)
    plt.close(fig)
    Image.open(root / "figures/headline.png").convert("RGB").save(
        root / "figures/headline.pdf", resolution=250
    )

    def response(p, variable):
        return v[(v.lag == p) & (v.variable == variable) & (v.method == "proxy VAR")].iloc[0]

    fx3, fx7 = response(3, "fx"), response(7, "fx")
    price3, price7 = response(3, "price"), response(7, "price")
    tr = csv("tr_identification_irfs.csv")
    trp = tr.query(
        'model == "TR_baseline" and method == "recursive" and variable == "price" and horizon == 12'
    ).iloc[0]
    title = "Euro area: a controlled methods comparison"
    question = "How do monetary-response estimates for the euro area and Türkiye depend on the shock-identification scheme and response estimator?"
    findings = [
        f"The euro appreciates after a tightening: the proxy estimate at month 12 is {fx3.estimate:.3f} log percent with p = 3 ({fx3.lo90:.3f}, {fx3.hi90:.3f}) and {fx7.estimate:.3f} with p = 7 ({fx7.lo90:.3f}, {fx7.hi90:.3f}); both conditional 90% bands exclude zero.",
        f"The price response is uncertain: proxy estimates at month 12 are {price3.estimate:.3f} and {price7.estimate:.3f} log percent, with both bands including zero. Estimates also change sign across methods.",
        f"For Türkiye, the recursive price estimate at month 12 is {trp.estimate:.3f} log percent. Recursive, FX-first and recursive-shock local-projection point estimates are negative, but their bands include zero.",
    ]
    method = "We compare recursive VAR, sign-restricted VAR, recursive-shock local projections and proxy VAR on a common euro-area sample, April 2005 to October 2025. Within each of two fixed lag panels, p = 3 and p = 7, we hold variables, transformations, deterministic terms and shock size constant and trace a 100-basis-point tightening over 36 months. We use bootstrap bands for VAR responses, HAC bands for local projections and separately labelled sign-admissible ranges. We also compare three Türkiye specifications and interpret proxy estimates conditional on instrument validity."
    limitations = [
        "Proxy exogeneity is assumed; its bands condition on fitted dynamics.",
        "Sign-admissible ranges are not statistical confidence intervals.",
        "Both common-sample VARs have slightly unstable dynamics.",
        "Local projections have fewer supported origins at longer horizons.",
        "Latest-vintage observations do not reconstruct real-time information.",
    ]
    sources = "ECB and Eurostat; CBRT/EVDS and TURKSTAT; FRED; the Euro Area Monetary Policy Event-Study Database (EA-MPD)."
    data = "ECB yields, Eurostat production/prices, CBRT/EVDS and TURKSTAT Türkiye series, FRED global controls, and EA-MPD policy-event surprises. [DATA.md](DATA.md) lists exact IDs, transformations, attribution and terms. Source observations are acquired through scripts and are not redistributed."
    extra = {"subtitle": "Euro area vs Türkiye", "secondary_figure": "figures/tr_price_note.png"}
    technical = "Historical decompositions and FEVDs use recursive Cholesky identification, separately from the proxy comparison. Annual decomposition summaries are annual averages of monthly log inflation, not annual inflation; month counts and partial-year coverage are reported. Proxy conclusions depend on instrument exogeneity and conditional inference. The technical working paper gives complete equations, diagnostics and robustness results."
elif name == "causal-ml-lab":
    nl = csv("v3_nonlinear_mc.csv").query('module == "DML"')
    sp = csv("v3_sparse_mc.csv")
    plugin = sp.query('method == "NaivePlugin"').iloc[0]
    dml = sp.query('method == "DML"').iloc[0]
    naive = nl.query('method == "NaiveML"').iloc[0]
    ndml = nl.query('method == "DML"').iloc[0]
    rf = csv("pension.csv").query('model == "IRM" and learner == "RF"').iloc[0]
    sens = csv("v3_rf_irm_sensitivity.csv").iloc[0]
    title = "Causal ML: shrinkage and identification"
    question = "When can regularization distort an estimated treatment effect, and what can cross-fitting and sensitivity diagnostics tell us?"
    findings = [
        f"In {int(dml.repetitions):,} sparse-design simulations, linear Lasso plug-in bias is {plugin.bias:.3f}, versus {dml.bias:.3f} for cross-fitted DML; 95% interval coverage is {100 * plugin.coverage:.1f}% versus {100 * dml.coverage:.1f}%.",
        f"Cross-fitting does not always improve the result: in the nonlinear design, in-sample orthogonal ML bias is {naive.bias:.3f}, versus {ndml.bias:.3f} for cross-fitted DML. These fixed-design comparisons do not establish a universal ranking.",
        f"In the historical SIPP sample, the RF-IRM estimate is ${rf.estimate:,.0f}. The sensitivity robustness values are {100 * sens.RV:.2f}% for the effect bound and {100 * sens.RVa:.2f}% for the confidence bound under the specified confounding model; they do not prove absence of confounding.",
    ]
    method = "We compare OLS, plug-in machine learning and cross-fitted double machine learning in two seeded designs with known treatment effects. We estimate 401(k) eligibility effects using partially linear and interactive models and examine propensity overlap and sensitivity to unobserved confounding. We compare staggered-adoption estimators and a late-cohort balanced event-study window using never-treated controls. We report Monte Carlo uncertainty, effect intervals and the assumptions required for causal interpretation."
    limitations = [
        "Designs and learner families differ; their rankings are not universal.",
        "IPW ESS measures weight concentration, not causal validity or propensity-estimation uncertainty.",
        "Historical eligibility is not randomized or modern policy participation.",
        "Balanced and full-sample event studies target different cohorts/windows.",
        "Group inference conditions on fitted nuisance models; transportability is untested.",
    ]
    sources = "Published 1991 SIPP extract via DoubleML; the did package's MPDTA county panel; seeded synthetic experiments."
    data = "The published 1991 SIPP extract is fetched at runtime through DoubleML; the MPDTA county panel comes from the did package. Synthetic designs are defined in code. [DATA.md](DATA.md) records citations and the analysis-only scope of dataset access. No microdata, row-level predictions or fitted objects are redistributed."
    extra = {}
    technical = "IPW ESS is a weight-concentration diagnostic; it does not include propensity-estimation uncertainty and is not a measure of causal validity. Clipping probabilities removes no observations. The balanced comparison uses cohorts 2006 and 2007 at event times -2, -1 and 0, with -1 as reference and constant cohort-size weights; its estimand differs from the full dynamic analysis. Income-quartile cutoffs are empirically computed, not forest-discovered groups. The technical working paper gives estimator equations, sensitivity definitions and simulation designs."
else:
    assert name == "inflation-forecast-nowcast"
    scores = csv("inflation_scores.csv")
    # Keep the seasonal benchmark result in the working paper, outside the brief.
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    models = ["RW", "AO", "AR", "BVAR", "Phillips", "LASSO", "Ensemble"]
    targets = ["ea_headline", "ea_core", "tr_headline"]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    matrix = np.array(
        [
            [
                scores[
                    (scores.target == t)
                    & (scores.model == m)
                    & (scores.horizon == 1)
                    & (scores.benchmark == "RW")
                ]
                .iloc[0]
                .relative_rmse
                for m in models
            ]
            for t in targets
        ]
    )
    ax.imshow(
        matrix,
        cmap=LinearSegmentedColormap.from_list("loss", ["#009E73", "white", "#D55E00"]),
        vmin=0.7,
        vmax=1.8,
        aspect="auto",
    )
    for i, target in enumerate(targets):
        for j, model in enumerate(models):
            r = scores[
                (scores.target == target)
                & (scores.model == model)
                & (scores.horizon == 1)
                & (scores.benchmark == "RW")
            ].iloc[0]
            ax.text(
                j,
                i,
                f"{r.relative_rmse:.2f}\n[{r.lo90:.2f}, {r.hi90:.2f}]",
                ha="center",
                va="center",
                fontsize=8,
            )
    ax.set(
        xticks=range(len(models)),
        xticklabels=["RW", "AO", "AR", "BVAR", "Phillips", "Lasso", "Ensemble"],
        yticks=range(3),
        yticklabels=["EA headline", "EA core", "Türkiye headline"],
        title="One-month fixed targets under publication lags",
    )
    fig.text(
        0.02,
        0.01,
        "RW = 1; 90% paired-block loss intervals. Same target dates and assumed availability calendar; latest vintage.",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(root / "figures/headline.png", dpi=300)
    fig.savefig(root / "figures/headline.pdf")
    plt.close(fig)

    def score(target, model, horizon=1):
        return scores[
            (scores.target == target)
            & (scores.model == model)
            & (scores.horizon == horizon)
            & (scores.benchmark == "RW")
        ].iloc[0]

    core, head = score("ea_core", "BVAR"), score("ea_headline", "Ensemble")
    bvar, ar = score("tr_headline", "BVAR", 12), score("tr_headline", "AR", 12)
    now = csv("nowcast_scores.csv")
    full = now[(now.model == "DFM") & (now.info_month == 3) & (~now.exclude_covid)].iloc[0]
    ex = now[(now.model == "DFM") & (now.info_month == 3) & now.exclude_covid].iloc[0]
    title = "Inflation forecasts with publication lags"
    question = "Do fixed inflation models improve on simple benchmarks when we respect assumed publication delays, and how sensitive are German GDP nowcasts to pandemic quarters?"
    findings = [
        f"With publication delays, EA core BVAR/RW RMSE is {core.relative_rmse:.3f} (90% loss interval {core.lo90:.3f}, {core.hi90:.3f}) and the EA headline ensemble/RW ratio is {head.relative_rmse:.3f} ({head.lo90:.3f}, {head.hi90:.3f}). These results do not support a general accuracy gain over the random walk.",
        f"Türkiye deteriorates at h = 12: BVAR/RW RMSE is {bvar.relative_rmse:.3f} and AR/RW is {ar.relative_rmse:.3f}. The 2021-23 inflation surge is consistent with difficult regime adaptation, but this comparison does not identify its separate causal contribution.",
        f"German GDP nowcasts are pandemic-sensitive: month-3 DFM/bridge RMSE is {full.relative_rmse:.3f} ({full.lo90:.3f}, {full.hi90:.3f}) overall and {ex.relative_rmse:.3f} ({ex.lo90:.3f}, {ex.hi90:.3f}) excluding 2020Q1-2021Q2. GDP is q/q log growth, not annualised.",
    ]
    method = "We forecast fixed year-on-year inflation targets at horizons of 1, 3, 6 and 12 months using expanding training windows and unchanged model settings. We assume final prices are published one month after their reference month and unemployment two months later, and forecast the extra steps from each effective data cutoff to the fixed target. We compare model errors against random-walk and Atkeson-Ohanian-style rules using paired loss intervals and fixed-bandwidth DM-HLN tests. We also compare bridge, MIDAS and factor nowcasts for German GDP under simulated release masks."
    limitations = [
        "Publication masks on latest-vintage data do not recreate historical vintages.",
        "The conservative unemployment delay reduces information for models using it.",
        "Fixed HAC and loss-bootstrap rules may leave dependence unaccounted for.",
        "Fixed learners and priors may adapt poorly to an inflation regime change.",
        "GDP rankings are pandemic-sensitive and some factor fits did not converge.",
    ]
    sources = "Eurostat and CBRT/EVDS-TURKSTAT. Atkeson and Ohanian (2001), DOI: 10.21034/qr.2511."
    data = "Eurostat supplies EA headline/core HICP, unemployment and German GDP/indicators; CBRT/EVDS-TURKSTAT supplies Türkiye prices and unemployment. [DATA.md](DATA.md) lists selectors, transformations and attribution. Scripts acquire observations at runtime; raw series and row-level forecasts are excluded."
    extra = {}
    technical = "This is publication-lag-adjusted, latest-vintage pseudo-real-time evaluation. Price and unemployment delays are assumptions, not exact historical release calendars. All models share target dates; target-only and complete-panel models use their appropriate effective cutoffs. The technical report presents the assumption-based seasonal-mean benchmark outside the ensemble, separate information-set/HAC comparisons and loss-bootstrap limitations."

requirements = "Python 3.11, uv and Tectonic" + (", plus R" if name == "causal-ml-lab" else "")
readme = (
    f"# {name}\n\n{question}\n\n![Headline](figures/headline.png)\n\n## Findings\n\n"
    + "\n".join("- " + f for f in findings)
)
readme += (
    f"\n\n## Method\n\n{method}\n\n## Data sources\n\n{data}\n\n## How to reproduce\n\nRequirements: {requirements}. Dependencies install inside the repository.\n\n```sh\nmake setup\nmake test lint quick\nmake policy-note report\n```\n\nThe last command rebuilds the notes and working paper from included aggregate results, without data acquisition or model fitting. `make quick` is offline and synthetic. Empirical acquisition/rerun commands, required credentials and source-vintage constraints are documented in [provenance and reproduction](docs/PROVENANCE.md).\n\n## Reports\n\n[Two-page policy note](report/policy_note.pdf) · [Technical working paper](report/technical_report.pdf) · [Detailed results](report/report.md)\n\n## Limitations\n\n"
    + "\n".join("- " + limitation for limitation in limitations)
)
readme += "\n\n## Licence\n\nOriginal code: [MIT](LICENSE). Third-party data retain their source terms and are not included.\n\nHakan Zeki Gülmez · [GitHub](https://github.com/hakangulmez) · [LinkedIn](https://www.linkedin.com/in/hakan-zeki-g%C3%BClmez-088700180/)\n"
write_note(root, title, question, method, findings, limitations, technical, sources, **extra)
(root / "README.md").write_text(readme)
(res / "findings.json").write_text(json.dumps(findings, indent=2) + "\n")
(res / "findings.md").write_text("\n".join("- " + f for f in findings) + "\n")
(root / "figures/linkedin/summary.txt").write_text(" ".join(findings) + "\n")
(res / "policy_note_lineage.json").write_text(
    json.dumps({"inputs": inputs, "render_only": True, "estimation": False}, indent=2) + "\n"
)
assert all(hashlib.sha256((res / f).read_bytes()).hexdigest() == h for f, h in inputs.items())
print(json.dumps({"repo": name, "findings": findings, "estimation": False}))
