# ruff: noqa: E501
"""All publication numbers are taken from machine-generated G3 tables."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from policy import write_note

from macro_var_lab.viz import PALETTE, apply_style

root = Path.cwd()
summary = json.loads((root / "results/g3_summary.json").read_text())
irf = pd.read_csv(root / "results/g3_irfs.csv")
figdir = root / "figures"
figdir.mkdir(exist_ok=True)
apply_style()
proxy = summary["proxy"]
proxy_ok = proxy.get("F", 0) > 10 and proxy["status"] == "identified_conditional"
preferred = "proxy" if proxy_ok else "recursive"


# One headline figure reports price, industrial production and EUR/USD through month 36.
def comparison(filename, specifications, heading):
    fig, axes = plt.subplots(1, 3, figsize=(9, 5.8))
    for ax, variable, label in zip(
        axes,
        ["price", "activity", "fx"],
        [
            "Prices",
            "Industrial production",
            "USD per EUR" if specifications[0][0].startswith("EA") else "TRY per USD",
        ],
        strict=True,
    ):
        non_sign_limits = []
        for j, (name, method, display) in enumerate(specifications):
            x = irf.query("model==@name and variable==@variable and method==@method").sort_values(
                "horizon"
            )
            ax.plot(
                x.horizon,
                x.estimate,
                color=PALETTE[j],
                label=display,
                lw=2.7 if method == preferred else 1.3,
                zorder=4 if method == "proxy" else 2,
            )
            if method == "sign_set":
                ax.plot(x.horizon, x["min"], color=PALETTE[j], lw=0.7, ls="--")
                ax.plot(x.horizon, x["max"], color=PALETTE[j], lw=0.7, ls="--")
            else:
                non_sign_limits.extend(x[["estimate", "lo90", "hi90"]].to_numpy().ravel())
                alpha = 0.26 if method == "proxy" else 0.07
                ax.fill_between(
                    x.horizon,
                    x.lo90,
                    x.hi90,
                    color=PALETTE[j],
                    alpha=alpha,
                    zorder=3 if method == "proxy" else 1,
                )
                ax.fill_between(
                    x.horizon,
                    x.lo68,
                    x.hi68,
                    color=PALETTE[j],
                    alpha=alpha,
                    zorder=3 if method == "proxy" else 1,
                )
        limits = np.asarray([value for value in non_sign_limits if np.isfinite(value)] + [0.0])
        lower, upper = float(limits.min()), float(limits.max())
        padding = max((upper - lower) * 0.06, 0.1)
        ax.set_ylim(lower - padding, upper + padding)
        ax.axhline(0, color=".5", lw=0.6)
        ax.set(title=label, xlabel="Months", ylabel="Response (100 x log change)", xlim=(0, 36))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.07), ncol=4, fontsize=10)
    fig.suptitle(heading, fontsize=15)
    fig.text(
        0.02,
        0.025,
        "100 bp tightening; darker proxy 68/90% bands. Dashed sign ranges are not confidence bands and may lie outside the view.\nY-limits use non-sign estimates/90% bands. Proxy ends 2025-10; others 2026-07. ECB/Eurostat/CBRT/FRED; author calculations.",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.18, 1, 0.93))
    fig.savefig(figdir / (filename + ".png"), dpi=300)
    fig.savefig(figdir / (filename + ".pdf"))
    plt.close(fig)


comparison(
    "headline",
    [
        ("EA_baseline", "recursive", "Recursive"),
        ("EA_baseline", "sign_set", "Signs (median)"),
        ("EA_baseline", "LP_HAC", "Local projections"),
        ("EA_proxy_overlap", "proxy", "Proxy (preferred)"),
    ],
    "Euro area: identification changes the answer",
)
comparison(
    "ea_proxy",
    [("EA_proxy_overlap", "proxy", "Event-window proxy")],
    "Euro area proxy: price, activity and exchange rate",
)
comparison(
    "tr_identification",
    [
        ("TR_baseline", "recursive", "Recursive"),
        ("TR_FX_first", "recursive", "FX first"),
        ("TR_baseline", "LP_HAC", "Local projections"),
    ],
    "Türkiye: the same estimates, three identification comparisons",
)
proxy_rows = irf.query('method=="proxy" and variable in ["price","activity","fx"]').copy()
proxy_rows.to_csv(root / "results/ea_proxy_irfs.csv", index=False)
comparison_rows = irf.query(
    'variable in ["price","activity","fx"] and ((model=="EA_baseline" and method in ["recursive","sign_set","LP_HAC"]) or method=="proxy")'
)
comparison_rows.to_csv(root / "results/ea_identification_irfs.csv", index=False)
tr_rows = irf.query(
    'variable in ["price","activity","fx"] and ((model=="TR_baseline" and method in ["recursive","LP_HAC"]) or (model=="TR_FX_first" and method=="recursive"))'
)
tr_rows.to_csv(root / "results/tr_identification_irfs.csv", index=False)
r = irf.query(
    'model=="EA_baseline" and variable=="price" and method=="recursive" and horizon==12'
).iloc[0]
lp_price = irf.query(
    'model=="EA_baseline" and variable=="price" and method=="LP_HAC" and horizon==12'
).iloc[0]
sign_price = irf.query(
    'model=="EA_baseline" and variable=="price" and method=="sign_set" and horizon==12'
).iloc[0]
p = proxy_rows.query('variable=="price" and horizon==12').iloc[0]
f = proxy_rows.query('variable=="fx" and horizon==12').iloc[0]
a = proxy_rows.query('variable=="activity" and horizon==12').iloc[0]
t = tr_rows.query(
    'model=="TR_baseline" and variable=="price" and method=="recursive" and horizon==12'
).iloc[0]
tx = tr_rows.query('model=="TR_FX_first" and variable=="price" and horizon==12').iloc[0]
tl = tr_rows.query(
    'model=="TR_baseline" and variable=="price" and method=="LP_HAC" and horizon==12'
).iloc[0]
findings = [
    f"The exchange-rate channel is clear: a year after tightening, the euro is {f.estimate:.3f}% stronger in the preferred proxy estimate, and its uncertainty interval stays above zero.",
    f"The price response is not pinned down: estimates change sign across identification methods, while the proxy estimate of {p.estimate:.3f}% has an uncertainty interval that includes zero.",
    f"Türkiye's price estimates are negative across the comparison methods but imprecise; the recursive estimate a year after tightening is {t.estimate:.3f}%.",
]
(root / "results/findings.json").write_text(json.dumps(findings, indent=2))
(root / "results/findings.md").write_text("\n".join("- " + x for x in findings) + "\n")
(root / "results/G3_REVIEW.md").write_text(
    "# V2 identification review\n\n"
    + "\n".join("- " + x for x in findings)
    + "\n\nProxy preferred conditionally on relevance and exclusion; see report/report.md for the different sample/lag and conditional-band caveats.\n"
)
(figdir / "linkedin").mkdir(exist_ok=True)
fig, ax = plt.subplots(figsize=(4, 4), dpi=300)
for j, (variable, label) in enumerate([("fx", "Euro appreciation"), ("price", "Price response")]):
    x = proxy_rows.query("variable==@variable")
    ax.plot(x.horizon, x.estimate, color=PALETTE[j], label=label)
    ax.fill_between(x.horizon, x.lo90, x.hi90, color=PALETTE[j], alpha=0.15)
ax.axhline(0, color=".5", lw=0.6)
ax.legend(fontsize=8)
ax.set(title="EA: currency channel is clearer", xlabel="Months", ylabel="Proxy response (log %)")
fig.text(
    0.02,
    0.01,
    "100 bp tightening; 90% pointwise bands.\nProxy sample ends October 2025. Official sources; local draft.",
    fontsize=6,
)
fig.tight_layout(rect=(0, 0.1, 1, 1))
fig.savefig(figdir / "linkedin/headline.png", dpi=300)
plt.close(fig)
(figdir / "linkedin/summary.txt").write_text(" ".join(findings) + "\n")
# FEVD and declared robustness comparisons have uncertainty bands.
for fname, models in [
    ("tr_robustness", ["TR_baseline", "TR_BIC", "TR_FX_first", "TR_easing_dummy"]),
    ("ea_robustness", ["EA_baseline", "EA_BIC", "EA_bundesbank_long", "EA_overnight_long"]),
]:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for j, name in enumerate(models):
        x = irf.query('model==@name and variable=="price" and method=="recursive"')
        ax.plot(x.horizon, x.estimate, color=PALETTE[j], label=name)
        ax.fill_between(x.horizon, x.lo90, x.hi90, color=PALETTE[j], alpha=0.08)
    ax.axhline(0, color=".4", lw=0.6)
    ax.legend(fontsize=8)
    ax.set_xlabel("Months")
    ax.set_ylabel("Price response (log %)")
    fig.text(
        0.02,
        0.015,
        (
            "90% pointwise Kilian bands. Samples/order differ as labelled.\n"
            "Source: Deutsche Bundesbank; monthly averages and transformations: author. "
            "Other sources: ECB/Eurostat/CBRT/FRED."
        )
        if fname == "ea_robustness"
        else "90% pointwise Kilian bands. Official macro sources; author calculations. Samples/order differ as labelled.",  # noqa: E501
        fontsize=7,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(figdir / (fname + ".png"), dpi=300)
    fig.savefig(figdir / (fname + ".pdf"))
    plt.close(fig)
fevd = pd.read_csv(root / "results/g3_fevd.csv")
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, area in zip(axes, ["EA", "TR"], strict=True):
    name = area + "_baseline"
    for j, variable in enumerate(["activity", "price", "fx"]):
        x = fevd.query("model==@name and variable==@variable")
        ax.plot(x.horizon, x.policy_share * 100, color=PALETTE[j], label=variable)
        ax.fill_between(x.horizon, x.lo90 * 100, x.hi90 * 100, color=PALETTE[j], alpha=0.12)
    ax.set_title(area)
    ax.set_xlabel("Months")
    ax.set_ylabel("Policy share (%)")
    ax.legend(fontsize=8)
fig.text(
    0.02,
    0.01,
    "90% block-bootstrap bands; finite-horizon decomposition, not stationary long-run shares.",
    fontsize=7,
)
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(figdir / "fevd.png", dpi=300)
fig.savefig(figdir / "fevd.pdf")
plt.close(fig)
# Identification and pass-through comparisons, with their own reported uncertainty.
for fname, names, methods in [
    ("tr_pass_through", ["TR_pass_through"], ["LP_HAC"]),
    ("bootstrap_comparison", ["EA_baseline", "EA_baseline"], ["recursive", "plain_block"]),
]:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for j, (name, method) in enumerate(zip(names, methods, strict=True)):
        x = irf.query('model==@name and variable=="price" and method==@method')
        ax.plot(x.horizon, x.estimate, color=PALETTE[j], label=name + " " + method)
        ax.fill_between(x.horizon, x.lo90, x.hi90, color=PALETTE[j], alpha=0.18)
    ax.axhline(0, color=".5", lw=0.6)
    ax.set(xlabel="Months", ylabel="Cumulative price response (log %)")
    ax.legend(fontsize=8)
    fig.text(
        0.02,
        0.02,
        "90% pointwise bands. Proxy: conditional slopes; pass-through: exact 10% depreciation. Official sources.",  # noqa: E501
        fontsize=7,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(figdir / (fname + ".png"), dpi=300)
    fig.savefig(figdir / (fname + ".pdf"))
    plt.close(fig)
hd = pd.read_csv(root / "results/g3_history_annual.csv")
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, area in zip(axes, ["EA", "TR"], strict=True):
    x = hd[hd.model == area + "_baseline"]
    ax.plot(x.year, x.mean_inflation, color=PALETTE[0], label="Observed annual mean")
    ax.plot(x.year, x.mean_policy_contribution, color=PALETTE[1], label="Policy contribution")
    ax.fill_between(x.year, x.lo90, x.hi90, color=PALETTE[1], alpha=0.18)
    ax.set(title=area, xlabel="Year", ylabel="Mean monthly inflation / contribution (pp)")
    ax.legend(fontsize=7)
fig.text(
    0.02,
    0.01,
    "90% plain moving-block parameter bands; annual aggregates, no row-level source data. Partial endpoint years.",  # noqa: E501
    fontsize=7,
)
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(figdir / "historical_decomposition.png", dpi=300)
fig.savefig(figdir / "historical_decomposition.pdf")
plt.close(fig)
for filename in [
    "g3_irfs",
    "g3_fevd",
    "g3_history_annual",
    "ea_proxy_irfs",
    "ea_identification_irfs",
    "tr_identification_irfs",
]:
    table = pd.read_csv(root / "results" / (filename + ".csv"))
    # Exact code-derived compact preview; full aggregate estimates remain in CSV.
    cols = table.columns.tolist()
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    lines += [
        "| " + " | ".join(map(str, row)) + " |"
        for row in table.head(20).itertuples(index=False, name=None)
    ]
    (root / "results" / (filename + ".md")).write_text(
        "\n".join(lines) + "\n\nFirst rows; complete estimates in companion CSV.\n"
    )

question = "How much does the euro area's response to a rate increase depend on how the policy shock is identified?"
method = "We compare four ways of isolating a 100-basis-point tightening in monthly euro-area data. We trace prices, industrial production and the exchange rate over 36 months, with uncertainty shown. We prefer the event-window proxy when its strength gate passes and retain the original Türkiye comparisons."
limitations = [
    "Proxy strength does not establish instrument validity.",
    "Proxy sample and lag differ from the other EA estimates.",
    "Sign ranges are not confidence intervals.",
    "Near-unit-root estimates make uncertainty fragile.",
    "Latest-vintage data do not reconstruct real-time information.",
]
technical = f"""The EA headline compares recursive, signs, direct cumulative-outcome HAC local projections and proxy identification. The proxy relevance gate holds (F={proxy["F"]:.6f}, {proxy["nobs"]} residual observations); this supports conditional preference under the review decision, not proof of exclusion. Combined Monetary Event Window, OIS_2Y; overlapping sample September 2004-October 2025, lag3 refit versus baseline lag7 through July 2026. Differences mix identification, sample and lag: not a controlled identification-only contrast. Later instrument months are missing, not zero. Proxy price and IP bands include zero; euro appreciation does not. The weak positive price response is a price puzzle, reported without tuning.

All proxy price/IP/FX horizons0-36 and 68/90 bands are in results/ea_proxy_irfs.csv. Paired residual-IV block bands condition on estimated VAR slopes; {proxy["bootstrap_successful"]} of 499 resamples pass the instrument-strength gate, with weak draws omitted. These are pointwise conditional intervals, not full-slope or weak-IV-robust confidence sets. Sign medians/ranges reflect restrictions imposing early disinflation; they are not sampling bands. For readability, the headline y-limits follow recursive/LP/proxy point estimates and90% bands; thin dashed admissible sign endpoints and sign medians may be outside this view. Full untrimmed endpoints remain in the aggregate tables. Display changes no estimate or accepted rotation. Percent responses here denote100 x log changes, as in the source IRFs. Recursive Kilian 200-bias/499 outer draws; ordinary block-bootstrap robustness, conditional on lag/transform selection. Equation BG order1 lag search is an intersection of marginal tests, not a system LR test; flagged BIC fallback where none passes. Initially unstable models are not forced into stationarity.

TR is unchanged: AOFM2011-01 to2026-07, approved price inflation transformation after levels diagnostics, lag9, remaining instability acknowledged. results/tr_identification_irfs.csv and figures/tr_identification show recursive, FX-first and LP side by side. Exchange-rate orientation: EA USD per EUR (increase=appreciation), TR TRY per USD (increase=depreciation). Ordering changes the TR response magnitude; at month12 all three point estimates are negative but imprecise. LP does not repair identification. Recent regime uses four-variable short-horizon LP only. Mixed integration blocks VECM; exact10% depreciation pass-through LP is labelled fallback. Annual historical aggregates/FEVD and original robustness tables retained; no new TR estimation.

Reproduction status is in results/reproduction_check.json; ECB public GET transient/network failures retry at most5 times with1,2,4,8-second exponential waits. Permanent errors stop immediately; final errors include the public endpoint and status without credentials. No raw redistribution. Theory references: Sims, Stock & Watson(1990),10.2307/2938337; Kilian(1998),10.1162/003465398557465; Jorda(2005),10.1257/0002828053828518; Altavilla et al.(2019),10.1016/j.jmoneco.2019.08.016."""
sources = "Sources: ECB/Eurostat/CBRT-TURKSTAT; Federal Reserve/EIA/CBOE via FRED. Author calculations; tables results/g3_irfs.csv and g3_summary.json."
# Compact price-only comparison for the second page, using unchanged TR estimates.
fig, ax = plt.subplots(figsize=(7, 2.4))
for j, (name, method_name, label) in enumerate(
    [
        ("TR_baseline", "recursive", "Recursive"),
        ("TR_FX_first", "recursive", "FX first"),
        ("TR_baseline", "LP_HAC", "Local projections"),
    ]
):
    x = tr_rows.query('model==@name and variable=="price" and method==@method_name')
    ax.plot(x.horizon, x.estimate, color=PALETTE[j], label=label)
    ax.fill_between(x.horizon, x.lo90, x.hi90, color=PALETTE[j], alpha=0.12)
    ax.fill_between(x.horizon, x.lo68, x.hi68, color=PALETTE[j], alpha=0.18)
ax.axhline(0, color=".5", lw=0.6)
ax.set(title="Türkiye: price response after tightening", xlabel="Months", ylabel="Response (log %)")
ax.legend(fontsize=9, ncol=3, loc="upper right")
fig.text(
    0.02,
    0.01,
    "100 bp tightening; 68/90% pointwise bands. CBRT-TURKSTAT/FRED; author calculations.",
    fontsize=7,
)
fig.tight_layout(rect=(0, 0.09, 1, 1))
fig.savefig(figdir / "tr_price_note.png", dpi=300)
fig.savefig(figdir / "tr_price_note.pdf")
plt.close(fig)

write_note(
    root,
    "Euro area: identification changes the answer",
    question,
    method,
    findings,
    limitations,
    technical,
    sources,
    subtitle="Euro area vs Türkiye",
    secondary_figure="figures/tr_price_note.png",
)
(root / "README.md").write_text(
    "# macro-var-lab\n\n"
    + question
    + "\n\n"
    + method
    + "\n\n![Headline](figures/headline.png)\n\n[Read the two-page policy note (PDF)](report/policy_note.pdf) · [Full technical report](report/report.md)\n\n## Findings\n\n"
    + "\n".join("- " + x for x in findings)
    + "\n\n## Reproduce\n\nInstall Python 3.11, uv and Git. Copy `.env.example` to `.env` and supply your own `FRED_API_KEY` and `EVDS_API_KEY`; values must stay private. `make setup all` acquires official data and builds results. `make quick` is isolated synthetic/offline; `make test lint`. See [reproduction notes](docs/REPRODUCTION.md). No raw redistribution.\n\n## Technical notes\n\n"
    + technical
    + "\n\n## Licence\n\nCode is MIT-licensed; third-party source data retain their original terms and are not included. Publication files and safety checks are documented in [docs/PUBLISH_CHECKLIST.md](docs/PUBLISH_CHECKLIST.md).\n\nHakan Zeki Gulmez | [GitHub](https://github.com/hakangulmez) | [LinkedIn](https://www.linkedin.com/in/hakan-zeki-g%C3%BClmez-088700180/)\n"
)
print(json.dumps(dict(findings=findings, proxy_preferred=proxy_ok)))
