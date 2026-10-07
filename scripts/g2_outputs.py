"""Generate G2 tables, figures and a one-page summary from estimates."""

import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from macro_var_lab.viz import PALETTE, apply_style, export

ROOT = Path.cwd()
SUMMARY = json.loads((ROOT / "results/g2_summary.json").read_text())
RUN = ROOT / "runs" / SUMMARY["analysis_id"]
IRF = pd.read_csv(ROOT / "results/g2_irfs.csv")
FEVD = pd.read_csv(ROOT / "results/g2_fevd.csv")
FIG = ROOT / "results/figures"
artifacts = []
SOURCE = (
    "Sources: Eurostat, ECB, CBRT/TURKSTAT, Bundesbank; Federal "
    "Reserve, EIA, CBOE via FRED.\n"
    "Author calculations; G1 revised-data vintage 7 Oct 2026."
)


def save(fig, path, note):
    fig.tight_layout(rect=(0, 0.16, 1, 0.94))
    scenario = (
        " Tightening = 100 bp; horizons in months."
        if path.name not in {"policy_fevd", "inflation_history", "core_growth_overlap"}
        else ""
    )
    if path.name == "core_growth_overlap":
        sources = "Sources: CBRT/EVDS and TURKSTAT; paired old/current histories."
    elif path.name.startswith("tr_") or path.parent.name.startswith("TR_"):
        sources = "Sources: CBRT/TURKSTAT; Federal Reserve, EIA, CBOE via FRED."
    elif path.name.startswith("ea_") or path.parent.name.startswith("EA_"):
        sources = "Sources: Eurostat, ECB; Federal Reserve, EIA, CBOE via FRED."
        if path.name == "ea_robustness":
            sources += " Deutsche Bundesbank (German-yield panel)."
    else:
        sources = "Sources: Eurostat, ECB, CBRT/TURKSTAT; Federal Reserve, EIA, CBOE via FRED."
    source = sources + "\nAuthor calculations; G1 revised-data vintage 7 Oct 2026."
    export(fig, path, source + scenario + "\n" + note)
    plt.close(fig)
    artifacts.append(str(path.relative_to(ROOT)))


def curve(ax, rows, color, label, bands=True, style="-"):
    rows = rows.sort_values("horizon")
    if bands:
        ax.fill_between(rows.horizon, rows.lo90, rows.hi90, color=color, alpha=0.10)
        ax.fill_between(rows.horizon, rows.lo68, rows.hi68, color=color, alpha=0.20)
    ax.plot(rows.horizon, rows.estimate, color=color, label=label, linestyle=style, linewidth=1.8)
    ax.axhline(0, color="0.4", linewidth=0.6)
    ax.set_xlabel("Months after tightening")


def rows(model, variable, method="recursive"):
    return IRF[(IRF.model == model) & (IRF.variable == variable) & (IRF.method == method)]


apply_style()
for area in ["EA", "TR"]:
    model = area + "_baseline"
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, variable, title in zip(
        axes.flat,
        ["activity", "price", "policy", "fx"],
        [
            "Industrial production (log %)",
            "Price level (log %)",
            "Policy indicator (pp)",
            "EUR/USD (log %; + appreciation)"
            if area == "EA"
            else "USD/TRY (log %; + depreciation)",
        ],
        strict=True,
    ):
        curve(ax, rows(model, variable), PALETTE[0], "Recursive")
        curve(ax, rows(model, variable, "LP_joint_bootstrap"), PALETTE[1], "LP", style="--")
        # Sign spread is deliberately unshaded to distinguish it from bootstrap confidence bands.
        sign = rows(model, variable, "sign_rotation_set").sort_values("horizon")
        curve(ax, sign, PALETTE[2], "Signs: median", bands=False, style=":")
        ax.plot(sign.horizon, sign.lo90, color=PALETTE[2], linewidth=0.7, linestyle=":")
        ax.plot(sign.horizon, sign.hi90, color=PALETTE[2], linewidth=0.7, linestyle=":")
        ax.set_title(title, fontsize=11)
    axes[0, 0].legend(fontsize=9)
    record = SUMMARY["models"][model]
    fig.suptitle(
        f"{area}: recursive, local projections and sign restrictions | lag {record['lag']}",
        fontsize=14,
    )
    save(
        fig,
        FIG / f"{area.lower()}_identification",
        "Shading: pointwise 68/90% joint bootstrap; green outer dotted "
        "lines: 90% rotation spread, NOT CI.\n"
        "Baseline VAR unstable. Finite-horizon estimates are diagnostic; "
        "TR price path accumulates monthly inflation.",
    )

for area, names in [
    (
        "EA",
        [
            "EA_baseline",
            "EA_core",
            "EA_growth",
            "EA_overnight_common",
            "EA_overnight_long",
            "EA_bundesbank_long",
        ],
    ),
    (
        "TR",
        [
            "TR_baseline",
            "TR_announced",
            "TR_core_b",
            "TR_core_c",
            "TR_growth",
            "TR_levels_comparison",
        ],
    ),
]:
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for ax, name in zip(axes.flat, names, strict=True):
        curve(ax, rows(name, "price"), PALETTE[0], name)
        base = rows(area + "_baseline", "price")
        ax.plot(
            base.horizon,
            base.estimate,
            color="0.5",
            linestyle="--",
            linewidth=1,
            label="Baseline reference",
        )
        radius = SUMMARY["models"][name]["residual_diagnostics"]["companion_spectral_radius"]
        ax.set_title(f"{name}\nroot {radius:.4f}", fontsize=9)
        ax.set_ylabel("Price level (log %)")
    axes.flat[1].legend(fontsize=7)
    fig.suptitle(f"{area}: all declared price-response robustness runs", fontsize=14)
    save(
        fig,
        FIG / f"{area.lower()}_robustness",
        "Shading: recursive 68/90% bootstrap. Long windows change the "
        "sample; differences cumulated for presentation.\n"
        + (
            "Source: Deutsche Bundesbank for German-yield panel; "
            "monthly averages/transformations: author."
            if area == "EA"
            else "Current-base cores; no splice or price-puzzle tuning."
        ),
    )

fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
for ax, name in zip(axes, ["TR_regime_1", "TR_regime_2", "TR_regime_3_LP"], strict=True):
    method = "LP_joint_bootstrap" if name.endswith("LP") else "recursive"
    curve(ax, rows(name, "price", method), PALETTE[0], method)
    ax.set_title(
        name
        + "\n"
        + str(SUMMARY["models"][name]["spec"]["start"])
        + " to "
        + str(SUMMARY["models"][name]["spec"]["end"]),
        fontsize=10,
    )
    ax.set_ylabel("Price level (log %)")
    if name.endswith("LP"):
        valid = rows(name, "price", method).dropna(subset=["estimate"]).horizon.max()
        ax.axvspan(valid + 0.5, 36, color="0.8", alpha=0.4)
        ax.text(0.48, 0.8, f"h > {valid:g}\nunavailable", transform=ax.transAxes, fontsize=10)
        ax.set_xlim(0, 36)
fig.suptitle("TR regimes: early/middle recursive VAR; recent four-variable LP only", fontsize=12)
save(
    fig,
    FIG / "tr_regimes",
    "68/90% bootstrap. Recent LP uses a retrospective full-sample "
    "recursive shock, one domestic lag, month dummies.\n"
    "No short-regime VAR; unavailable horizons are not extrapolated. "
    "Short-window identification is especially fragile.",
)

fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
for ax, area in zip(axes, ["EA", "TR"], strict=True):
    for j, variable in enumerate(["activity", "price", "fx"]):
        x = FEVD[
            (FEVD.model == area + "_baseline")
            & (FEVD.variable == variable)
            & (FEVD.shock == "policy")
        ]
        ax.plot(x.horizon, x.share * 100, color=PALETTE[j], label=variable)
        ax.fill_between(x.horizon, x.lo90 * 100, x.hi90 * 100, color=PALETTE[j], alpha=0.10)
        ax.fill_between(x.horizon, x.lo68 * 100, x.hi68 * 100, color=PALETTE[j], alpha=0.18)
    ax.set_title(
        area + ("; price = monthly inflation" if area == "TR" else "; price = log level"),
        fontsize=11,
    )
    ax.set_xlabel("Forecast horizon (months)")
    ax.set_ylabel("Policy shock share (%)")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=9)
fig.suptitle("Recursive finite-horizon forecast-error variance decomposition")
save(
    fig,
    FIG / "policy_fevd",
    "Pointwise 68/90% bootstrap. Shares sum to one across ALL shocks; "
    "no stationary long-run interpretation.",
)

inflation_rows = []
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
for ax, area in zip(axes, ["EA", "TR"], strict=True):
    name = area + "_baseline"
    j = SUMMARY["models"][name]["variables"].index("price")
    with np.load(RUN / name / "bootstrap.npz") as cached:
        for method, key, color in [
            ("recursive", "var", PALETTE[0]),
            ("LP_joint_bootstrap", "lp", PALETTE[1]),
        ]:
            level = rows(name, "price", method).sort_values("horizon")
            point = np.diff(level.estimate.to_numpy(), prepend=0)
            samples = np.diff(cached[key][:, :, j], axis=1, prepend=np.zeros((len(cached[key]), 1)))
            bands = np.quantile(samples, [0.05, 0.16, 0.84, 0.95], axis=0)
            table = pd.DataFrame(
                {
                    "horizon": level.horizon,
                    "estimate": point,
                    "lo90": bands[0],
                    "lo68": bands[1],
                    "hi68": bands[2],
                    "hi90": bands[3],
                }
            )
            curve(ax, table, color, method)
            inflation_rows.extend(table.assign(model=name, method=method).to_dict("records"))
    ax.set_title(area + ": monthly inflation response")
    ax.set_ylabel("100 x monthly log change (pp)")
    ax.legend(fontsize=8)
fig.suptitle("Monthly inflation: differencing price paths within every draw")
save(
    fig,
    FIG / "monthly_inflation_irfs",
    "Shading: pointwise 68/90% joint bootstrap. Monthly inflation, "
    "not price levels.\n"
    "Sign medians are not differenced into a fictitious native median. "
    "Both baseline VARs remain unstable.",
)
pd.DataFrame(inflation_rows).to_csv(ROOT / "results/g2_inflation_irfs.csv", index=False)

for area in ["EA", "TR"]:
    name = area + "_baseline"
    history = pd.read_csv(RUN / name / "inflation_history_private.csv", index_col=0)
    history.index = pd.PeriodIndex(history.index, freq="M").to_timestamp()
    with np.load(RUN / name / "bootstrap.npz") as data:
        draws = data["history"][:, -len(history) :]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    columns = SUMMARY["models"][name]["variables"] + ["initial_deterministic"]
    components = history[columns].to_numpy().T
    colors = (PALETTE + ["#F0E442", "#888888"])[: len(columns)]
    axes[0].stackplot(
        history.index, np.maximum(components, 0), colors=colors, labels=columns, alpha=0.55
    )
    axes[0].stackplot(history.index, np.minimum(components, 0), colors=colors, alpha=0.55)
    axes[0].plot(
        history.index,
        history.reconstruction,
        color="black",
        linewidth=1.2,
        label="Observed monthly inflation",
    )
    axes[0].set_ylabel("Inflation components (pp)")
    axes[0].legend(fontsize=7, ncol=3)
    axes[1].plot(
        history.index,
        history.policy,
        color=PALETTE[0],
        label="Identified policy-shock contribution",
    )
    axes[1].fill_between(
        history.index,
        np.quantile(draws, 0.05, axis=0),
        np.quantile(draws, 0.95, axis=0),
        color=PALETTE[0],
        alpha=0.10,
    )
    axes[1].fill_between(
        history.index,
        np.quantile(draws, 0.16, axis=0),
        np.quantile(draws, 0.84, axis=0),
        color=PALETTE[0],
        alpha=0.22,
    )
    axes[1].axhline(0, color="0.4", linewidth=0.7)
    axes[1].set_ylabel("Inflation contribution (pp)")
    axes[1].legend(fontsize=9)
    fig.suptitle(f"{area}: inflation historical decomposition (private review figure)", fontsize=13)
    save(
        fig,
        RUN / name / "inflation_history",
        "Policy-contribution shading: 68/90% parameter-bootstrap bands "
        "conditional on actual observed history.\n"
        "Top: all signed shock + initial/deterministic components; exact "
        "private accounting. No historical causality or welfare claim.",
    )

frame = pd.read_csv(ROOT / "data/processed/baseline_levels.csv", index_col=0)
frame.index = pd.PeriodIndex(frame.index, freq="M")
fig, axes = plt.subplots(2, 2, figsize=(11, 7))
for col, letter in enumerate(["b", "c"]):
    current = frame[f"tr_core_{letter}"].diff()
    old = frame[f"tr_core_{letter}_old"].diff()
    common = pd.concat([current.rename("current"), old.rename("old")], axis=1).dropna()
    time = common.index.to_timestamp()
    axes[0, col].plot(time, common.current, color=PALETTE[0], label="Current base 2025=100")
    axes[0, col].plot(
        time, common.old, color=PALETTE[1], linestyle="--", label="Archived base 2003=100"
    )
    axes[0, col].set_title(f"Core {letter.upper()}: overlap monthly growth")
    axes[0, col].set_ylabel("100 x monthly log change")
    axes[0, col].legend(fontsize=9)
    axes[1, col].plot(time, common.current - common.old, color=PALETTE[3])
    axes[1, col].axhline(0, color="0.4", linewidth=0.7)
    axes[1, col].set_ylabel("Current - old growth (pp)")
fig.suptitle("TR core rebasing check: incompatible histories, no splice", fontsize=13)
save(
    fig,
    RUN / "core_growth_overlap",
    "Descriptive paired growth, no uncertainty bands. Fixed ratio "
    "tolerance 0.2% fails for B (0.200031%) and C (0.207526%).\n"
    "These are ratio-range failures, not a 0.2 pp growth-gap "
    "threshold. Current-base complete target history used.",
)

# One table joins model choice and actual residual tests; no manual transcriptions.
diagnostic_rows = []
for name, record in SUMMARY["models"].items():
    if record.get("no_VAR_estimated"):
        diagnostic_rows.append(
            dict(model=name, months=record["months"], lag=record["lag"], kind="LP only")
        )
        continue
    diag = record["residual_diagnostics"]
    diagnostic_rows.append(
        dict(
            model=name,
            months=record["months"],
            lag=record["lag"],
            kind=record["spec"]["kind"],
            radius=diag["companion_spectral_radius"],
            stable=diag["stable"],
            AIC_lag=min(record["lag_selection"], key=lambda x: x["AIC"])["lag"],
            HQ_lag=min(record["lag_selection"], key=lambda x: x["HQ"])["lag"],
            BG_1_reject=sum(
                x.get("pvalue", 1) < 0.05 for x in [v["1"] for v in diag["BG_LM"].values()]
            ),
            BG_6_reject=sum(
                x.get("pvalue", 1) < 0.05 for x in [v["6"] for v in diag["BG_LM"].values()]
            ),
            BG_12_unavailable=sum("pvalue" not in v["12"] for v in diag["BG_LM"].values()),
            JB_marginal_reject=sum(v["pvalue"] < 0.05 for v in diag["JB_marginal"].values()),
        )
    )
pd.DataFrame(diagnostic_rows).to_csv(ROOT / "results/g2_diagnostics.csv", index=False)
unit_rows = []
for name, record in SUMMARY["unit_root_tests"].items():
    for transform in ["level", "first_difference"]:
        for test, item in record[transform].items():
            if isinstance(item, dict) and "pvalue" in item:
                unit_rows.append(
                    dict(
                        variable=name,
                        sample="2006-01:2026-07",
                        transform=transform,
                        test=test,
                        **item,
                    )
                )
for transform, record in SUMMARY["TR_transform_decision"]["baseline_CPI_unit_roots"].items():
    if isinstance(record, dict):
        for test, item in record.items():
            if isinstance(item, dict) and "pvalue" in item:
                unit_rows.append(
                    dict(
                        variable="tr_cpi",
                        sample="2011-01:2026-07",
                        transform=transform,
                        test=test,
                        **item,
                    )
                )
pd.DataFrame(unit_rows).to_csv(ROOT / "results/g2_unit_roots.csv", index=False)

headlines = []
for area in ["EA", "TR"]:
    for variable in ["activity", "price", "fx"]:
        for h in [6, 12, 24, 36]:
            x = rows(area + "_baseline", variable).query("horizon == @h").iloc[0]
            headlines.append(
                dict(
                    area=area,
                    variable=variable,
                    horizon=h,
                    estimate=x.estimate,
                    lo90=x.lo90,
                    hi90=x.hi90,
                )
            )
pd.DataFrame(headlines).to_csv(ROOT / "results/g2_headlines.csv", index=False)

ea_record = SUMMARY["models"]["EA_baseline"]
tr_record = SUMMARY["models"]["TR_baseline"]
tr_decision = SUMMARY["TR_transform_decision"]
cpi_diff = tr_decision["baseline_CPI_unit_roots"]["first_difference"]
ea_radius = ea_record["residual_diagnostics"]["companion_spectral_radius"]
tr_radius = tr_record["residual_diagnostics"]["companion_spectral_radius"]

lines = [
    "# M1 G2 - Finite-horizon monetary transmission",
    "**7 October 2026 | G2 complete; awaiting review | No G3 work or paid calls**",
    f"**Baseline diagnostics.** EA: Sep 2004-Jul 2026, {ea_record['months']} "
    f"months, BIC lag {ea_record['lag']}. TR: Jan 2011-Jul 2026, "
    f"{tr_record['months']} months, BIC lag {tr_record['lag']}. "
    f"TR levels root {tr_decision['levels_radius']:.5f} triggers monthly inflation. "
    f"EA levels root {ea_radius:.5f} "
    f"and TR inflation root {tr_radius:.5f} "
    "remain unstable. Finite-horizon responses and bands are diagnostic, "
    "not reliable stationary long-run evidence. "
    "No further stability/puzzle tuning. Residual autocorrelation "
    "and marginal non-normality remain.",
    "**Recursive 100 bp tightening: 12-month responses** (log %, with "
    "pointwise 90% bootstrap interval; TR price is accumulated "
    "monthly inflation).",
    "| Area | Industrial production | Price level | FX |",
    "|:--|--:|--:|--:|",
]
for area in ["EA", "TR"]:
    cells = []
    for variable in ["activity", "price", "fx"]:
        x = rows(area + "_baseline", variable).query("horizon == 12").iloc[0]
        cells.append(f"{x.estimate:.2f} [{x.lo90:.2f}, {x.hi90:.2f}]")
    lines.append("| " + area + " | " + " | ".join(cells) + " |")
lines += [
    "FX: EUR/USD rises with EUR appreciation; USD/TRY rises with TRY depreciation.",
    "**Identification and puzzles.**",
]
for area in ["EA", "TR"]:
    p = rows(area + "_baseline", "price").query("horizon == 12").iloc[0]
    fx = rows(area + "_baseline", "fx").query("horizon == 12").iloc[0]
    sign = rows(area + "_baseline", "price", "sign_rotation_set").query("horizon == 12").iloc[0]
    lp = rows(area + "_baseline", "price", "LP_joint_bootstrap").query("horizon == 12").iloc[0]
    price_path = rows(area + "_baseline", "price").query("horizon > 0")
    wrong_price = price_path[price_path.estimate > 1e-8]
    fx_path = rows(area + "_baseline", "fx")
    wrong_fx = (
        fx_path[fx_path.estimate < -1e-8] if area == "EA" else fx_path[fx_path.estimate > 1e-8]
    )
    clues = []
    if len(wrong_price):
        clues.append(f"positive-price point response first at month {wrong_price.horizon.min():g}")
    if len(wrong_fx):
        x = wrong_fx.iloc[0]
        clues.append(
            f"FX puzzle at month {x.horizon:g}: {x.estimate:+.2f} [{x.lo90:.2f}, {x.hi90:.2f}]"
        )
    if not clues:
        clues.append("no positive-price or depreciation point puzzle over 0-36")
    lines.append(
        f"{area}: "
        + "; ".join(clues)
        + f". At month 12, price LP {lp.estimate:.2f}; sign median {sign.estimate:.2f}. "
        "Sign spread is not a CI; initial price direction is imposed. "
        "Point puzzles can have bands crossing zero."
    )
share = []
for area in ["EA", "TR"]:
    x = FEVD[
        (FEVD.model == area + "_baseline")
        & (FEVD.variable == "price")
        & (FEVD.shock == "policy")
        & (FEVD.horizon == 12)
    ].iloc[0]
    share.append(f"{area} {x.share * 100:.2f}% [{x.lo90 * 100:.2f}, {x.hi90 * 100:.2f}]")
lines += [
    "**FEVD / decomposition.** Policy-shock price variance share at 12 months: "
    + "; ".join(share)
    + " (90% interval; EA log-price, TR monthly-inflation variance). "
    "Inflation histories reconstruct to numerical precision; "
    "initial/deterministic and all shock components retained "
    "privately.",
    "**Coverage and conditional work.** 14 VARs (499 joint "
    "residual-block bootstraps each), one four-variable recent-regime "
    "LP, 1,000 accepted sign directions per VAR. "
    "The Jun 2023-Jul 2026 regime contains 38 months; only supported "
    "LP horizons 0-8 are shown; later horizons unavailable. Full-sample shocks are retrospective, "
    "rescaled by each recent-regime impact response. "
    f"TR baseline CPI first-difference ADF p={cpi_diff['ADF_c']['pvalue']:.3f}, "
    f"KPSS p={cpi_diff['KPSS_c']['pvalue']:.2f} disagree; "
    "mixed CPI/FX I(1) evidence prevents Johansen/VECM; no silent "
    "gate relaxation. Core B/C ratios fail the fixed 0.2% bridge "
    "tolerance; growth-overlap figure provided, no splice.",
    "**Open questions for review.** How should unstable roots, "
    "residual autocorrelation/non-normality and broad uncertainty "
    "limit the economic interpretation? "
    "Do results describe endogenous indicator innovations rather than "
    "exogenous monetary decisions? "
    "All robustness runs are declared: core prices, growth variables "
    "(rates remain levels), overnight/common and long windows, German "
    "2y yield, announced TR policy comparator, preserved TR levels, "
    "and three regimes. "
    "No raw redistribution; sources and methods: DATA.md and G2_METHODS.md.",
]
(ROOT / "docs/G2_SUMMARY.md").write_text(
    "\n\n".join(lines[:4]) + "\n\n" + "\n".join(lines[4:8]) + "\n\n" + "\n\n".join(lines[8:]) + "\n"
)
# Markdown table must remain consecutive; the generated paragraphs can be separate.
text = (ROOT / "docs/G2_SUMMARY.md").read_text()
text = text.replace("\n\n|:--|", "\n|:--|")
(ROOT / "docs/G2_SUMMARY.md").write_text(text)
review = [
    "# G2 results index - awaiting review",
    "",
    "[One-page summary](G2_SUMMARY.md) | [Methods](G2_METHODS.md) | [Source rights](../DATA.md)",
    "",
    "Author estimates, not a validated monetary-policy causal effect. "
    "Both baseline VARs are unstable. "
    "No G3 work or publication. Tables and figures below are generated from recorded estimates.",
    "",
    "## Tables",
    "",
]
for filename in [
    "g2_headlines.csv",
    "g2_irfs.csv",
    "g2_inflation_irfs.csv",
    "g2_fevd.csv",
    "g2_diagnostics.csv",
    "g2_lag_selection.csv",
    "g2_unit_roots.csv",
    "g2_lp_hac.csv",
]:
    review.append(f"- [{filename}](../results/{filename})")
review += [
    "",
    "Native LP HAC: native transformed outcomes; recent LP SE conditional "
    "on estimated impact divisor. "
    "Use joint bootstrap for divisor/accumulation uncertainty. "
    "FEVD native price variable: EA level, TR inflation.",
    "",
    "## Figure review",
    "",
]
for name in artifacts:
    if name.startswith("runs/"):
        review.append(
            f"- Private review: [{Path(name).name}](../{name}.png); "
            "source-derived history not in Git."
        )
    else:
        review += [f"### {Path(name).name}", "", f"![{Path(name).name}](../{name}.png)", ""]
review += [
    "",
    "## Unit-root screen (p-values)",
    "",
    "Trend-level ADF/KPSS; constant first-difference ADF/PP/KPSS. "
    "CPI/FX/REER longer window 2006-01:2026-07. "
    "Diagnostic tests do not prove integration order.",
    "",
    "| Variable | ADF level ct | KPSS level ct | ADF diff c | "
    "PP diff c | KPSS diff c | I(1) agreement |",
    "|:--|--:|--:|--:|--:|--:|:--|",
]
for variable, record in SUMMARY["unit_root_tests"].items():
    values = [
        record["level"]["ADF_ct"]["pvalue"],
        record["level"]["KPSS_ct"]["pvalue"],
        record["first_difference"]["ADF_c"]["pvalue"],
        record["first_difference"]["PP_c"]["pvalue"],
        record["first_difference"]["KPSS_c"]["pvalue"],
    ]
    review.append(
        "| "
        + variable
        + " | "
        + " | ".join(f"{p:.4g}" for p in values)
        + " | "
        + str(record["I1_established_by_agreement_rule"])
        + " |"
    )
review += ["", "TR CPI baseline 2011-01:2026-07:", ""]
for transform in ["log_level", "first_difference"]:
    record = SUMMARY["TR_transform_decision"]["baseline_CPI_unit_roots"][transform]
    review.append(
        f"- {transform}: "
        + "; ".join(
            f"{test} p={record[test]['pvalue']:.4g}"
            for test in ["ADF_c", "PP_c", "KPSS_c", "ADF_ct", "PP_ct", "KPSS_ct"]
        )
    )
review += [
    "",
    "## Accounting and runtime",
    "",
    f"Analysis `{SUMMARY['analysis_id']}`; G1 `{SUMMARY['G1_run']}`; "
    f"full estimation {SUMMARY['elapsed_seconds']:.2f} s, "
    f"peak RSS {SUMMARY['peak_rss_bytes'] / 2**20:.1f} MiB, paid calls 0.",
    "",
    "Puzzles are retained; the EA price point changes sign later and TR initially depreciates. "
    "No lag/sample/order search is used to remove them. "
    "Sign restrictions impose initial disinflation.",
    "",
    "Local review only; no raw source observations or private historical tables are redistributed.",
]
(ROOT / "docs/G2_RESULTS.md").write_text("\n".join(review) + "\n")
manifest = {
    "analysis_id": SUMMARY["analysis_id"],
    "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "artifacts": {
        name + suffix: hashlib.sha256((ROOT / (name + suffix)).read_bytes()).hexdigest()
        for name in artifacts
        for suffix in [".png", ".pdf"]
    },
    "private_artifacts_not_in_git": [x for x in artifacts if x.startswith("runs/")],
    "PNG_dpi": 300,
    "sources": "G1 pinned revised-data files; no downloads",
}
(ROOT / "results/g2_artifacts.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Generated ten paired PNG/PDF figures, aggregate tables and G2_SUMMARY.md.")
