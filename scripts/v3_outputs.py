# ruff: noqa: E501
"""Present controlled comparison and identified inherited accounting; no estimation."""

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image
from policy import write_note

root = Path(__file__).resolve().parents[1]
res = root / "results"
v = pd.read_csv(res / "v3_methods_comparison.csv")
manifest = json.loads((res / "v3_methods_manifest.json").read_text())
s = json.loads((res / "g3_summary.json").read_text())
old = json.loads((root / "versions/v2-2026-10-07/results/g3_summary.json").read_text())
# Exact residual-date metadata on the historic all-shock FEVD, numeric shares unchanged.
p = res / "g2_fevd.csv"
fe = pd.read_csv(p)
g2 = json.loads((res / "g2_summary.json").read_text())
for name in fe.model.unique():
    model = g2["models"][name]
    lag = model["lag"]
    start = str(pd.Period(model["spec"]["start"], "M") + lag)
    mask = fe.model == name
    fe.loc[mask, "identification"] = "recursive Cholesky"
    fe.loc[mask, "sample_start"] = start
    fe.loc[mask, "sample_end"] = model["spec"]["end"]
    fe.loc[mask, "lag"] = lag
    fe.loc[mask, "units"] = (
        "fraction of forecast-error variance in native model outcome, not percent"
    )
fe.to_csv(p, index=False)
# Granger before/after bug evidence; no unaffected diagnostic changes.
rows = []
for name, m in s["models"].items():
    if "diagnostics" in m and name in old["models"]:
        d = m["diagnostics"]
        before = old["models"][name]["diagnostics"]
        rows.append(
            dict(
                model=name,
                selected_variable=d.get("granger_tested_variable", "policy"),
                policy_column=d.get("granger_policy_column"),
                v2_p=before.get("granger_policy_to", {}).get("price", {}).get("pvalue"),
                v3_p=d.get("granger_policy_to", {}).get("price", {}).get("pvalue"),
            )
        )
pd.DataFrame(rows).to_csv(res / "v3_granger_changes.csv", index=False)
# A fixed methods base sample and horizon-specific LP supported origin dates.
irfs = pd.read_csv(res / "v3_methods_irfs.csv")
irfs["units"] = irfs.variable.map(
    lambda variable: (
        "pp response per100bp tightening"
        if variable == "policy"
        else "unscaled log response per100bp tightening"
        if variable == "vix"
        else "100 log response per100bp tightening"
    )
)
mask = irfs.method == "recursive-shock LP"
irfs.loc[mask, "LP_origin_start"] = "2005-04"
irfs.loc[mask, "LP_origin_end"] = irfs.loc[mask, "horizon"].map(
    lambda h: str(pd.Period("2025-10", "M") - int(h))
)
irfs.to_csv(res / "v3_methods_irfs.csv", index=False)
pd.DataFrame(
    [
        dict(
            lag=int(k),
            status="completed",
            usable_start=d["usable_sample"][0],
            usable_end=d["usable_sample"][1],
            nobs=d["nobs"],
            F=d["proxy"]["F"],
            proxy_status=d["proxy"]["status"],
        )
        for k, d in manifest["panels"].items()
    ]
).to_csv(res / "v3_methods_status.csv", index=False)
shutil.copyfile(root / "figures/v3_methods_comparison.png", root / "figures/headline.png")
Image.open(root / "figures/headline.png").convert("RGB").save(
    root / "figures/headline.pdf", resolution=250
)


def row(p, var):
    return v[(v.lag == p) & (v.variable == var) & (v.method == "proxy VAR")].iloc[0]


fx3 = row(3, "fx")
fx7 = row(7, "fx")
p3 = row(3, "price")
p7 = row(7, "price")
tr = pd.read_csv(res / "tr_identification_irfs.csv")
trp = tr[
    (tr.model == "TR_baseline")
    & (tr.method == "recursive")
    & (tr.variable == "price")
    & (tr.horizon == 12)
].iloc[0]
findings = [
    f"On the common sample, proxy euro appreciation at month twelve is {fx3.estimate:.3f} log percent at p=3 ({fx3.lo90:.3f}, {fx3.hi90:.3f}) and {fx7.estimate:.3f} at p=7 ({fx7.lo90:.3f}, {fx7.hi90:.3f}); both conditional 90% bands exclude zero.",
    f"The price response remains imprecise: proxy month-twelve estimates are {p3.estimate:.3f} at p=3 and {p7.estimate:.3f} at p=7, with both bands including zero. Sign restrictions impose early disinflation; their ranges are not confidence intervals.",
    f"Türkiye results are inherited: recursive month-twelve price response is {trp.estimate:.3f} log percent. Recursive, FX-first and recursive-shock LP price point estimates remain negative but imprecise.",
]
future = "Instrument exogeneity/information-shock separation and alternative event windows; serial-dependence-robust strength tests and weak-IV/full-estimation-chain bands; persistence-robust LP; shrinkage, dimension and break diagnostics; TR intervention/indicator/regime comparability; sign-rotation and restriction-duration sensitivity; economically interpretable counterfactual policy paths. These substantive review extensions are deferred."
technical = f"""V3 methods comparison on a common sample and lag specification: April2005–October2025,247 usable VAR observations for both p3 and p7; September2004–March2005 supplies lag history only. The user authorized this mechanical start adjustment before comparison results because the frozen yield starts September2004. All original frozen inputs remain unchanged. Six variables, existing transforms, intercept/month indicators,100bp shock and36-month horizons fixed within each panel. Response estimators differ: recursive-shock LP uses the recursive innovation and VAR-design/ordered-predecessor controls, with horizon-specific supported origins247−h (235 at h12). It is not an identification-only contrast.

Proxy instrument remains combined EA-MPD Monetary Event Window/OIS_2Y. First-stage F p3={manifest["panels"]["3"]["proxy"]["F"]:.6f},p7={manifest["panels"]["7"]["proxy"]["F"]:.6f}; both exceed the unchanged10 threshold. Exogeneity is not established. Conditional paired block6 inference fixes VAR propagation slopes and omits weak draws: p3 accepted{manifest["panels"]["3"]["proxy"]["successful_draws"]}/499,p7 accepted{manifest["panels"]["7"]["proxy"]["successful_draws"]}/499. This is not weak-IV-robust/full-chain inference. Recursive iid Kilian bias200/outer499, original sign restrictions1000 admissible rotations, existing LP HAC remain. Sign medians/ranges may lie beyond figure limits; full ranges are in CSV. Neither lag was selected by narrative or significance. Spectral radii p3={manifest["panels"]["3"]["radius"]:.6f},p7={manifest["panels"]["7"]["radius"]:.6f} exceed one; unstable dynamics remain visible.

Inherited TR IRFs, regimes, transformations and original alternatives are unchanged. The policy-column bug is fixed by labels.index('policy'), with invariant reorder tests and only affected Granger entries regenerated. Historical accounting remains inherited recursive Cholesky, not proxy accounting. FEVD fractions describe native outcomes (EA price levels; TR monthly inflation), unnormalized unit-variance shocks; exported tables name sample,lag and units. HD reports arithmetic annual averages of monthly100ΔlogP in percentage points, NOT annual/cumulative inflation. Native TR inflation uses the same scale. Coverage and number of months appear for every year;2026 contains January–July,seven months,without annualisation. Components reconcile with represented levels/monthly inflation, with checks in v3_hd_accounting.json. This descriptive decomposition is not a structural explanation of each episode or a policy counterfactual.

New V3 methods outputs are distinct from inherited g3_irfs/ea_proxy_irfs and original full-window accounting. The private archive retains original V2 hashes; only required frozen aggregate regression fixtures are included publicly. Protocol, source workbook, processed data and private bootstrap lineage are recorded in V3 manifests. No raw data, private shocks or fitted objects are committed.
"""
write_note(
    root,
    "Euro area: a controlled methods comparison",
    "How do monetary-response estimates differ on the same usable sample and fixed lag specification?",
    "We compare recursive VAR, sign-restricted VAR, recursive-shock local projections and proxy VAR on the same usable monthly sample. We report both fixed lag panels and trace a 100-basis-point tightening over thirty-six months. We retain the original Türkiye comparisons and interpret proxy evidence conditionally on instrument validity.",
    findings,
    [
        "Proxy exogeneity remains an assumption; bands condition on fitted dynamics.",
        "Sign-admissible ranges are not confidence intervals.",
        "Both common-sample VARs remain slightly unstable.",
        "LP uses fewer supported origins at longer horizons.",
        "Latest-vintage observations do not recreate real-time information.",
    ],
    technical + "\n\nLimitations and future work: " + future,
    "Sources: frozen ECB/Eurostat/CBRT-TURKSTAT/FRED and EA-MPD. V3 methods CSVs; inherited TR and recursive accounting.",
    subtitle="Euro area vs Türkiye",
    secondary_figure="figures/tr_price_note.png",
)
(res / "findings.json").write_text(json.dumps(findings, indent=2) + "\n")
(res / "findings.md").write_text("\n".join("- " + f for f in findings) + "\n")
(root / "README.md").write_text(
    "# macro-var-lab\n\nMethods comparison on a common sample and lag specification: euro area vs Türkiye.\n\n![Headline](figures/headline.png)\n\n[Two-page policy note](report/policy_note.pdf) · [Technical working paper](report/technical_report.pdf) · [Results and assumptions](report/report.md)\n\n## Findings\n\n"
    + "\n".join("- " + f for f in findings)
    + "\n\n## Reproduce\n\n`make setup`; V3 uses existing frozen local inputs only. `make v3-methods v3-outputs report`; `make test lint`; `make quick` is synthetic/offline. Original acquisition via `make all` is a separate historical pipeline, not part of V3. Code MIT; source observations private under their terms, IDs/scripts in DATA.md.\n\n## Technical notes\n\n"
    + technical
    + "\n\n## Limitations and future work\n\n"
    + future
    + "\n\nHakan Zeki Gülmez | [GitHub](https://github.com/hakangulmez) | [LinkedIn](https://www.linkedin.com/in/hakan-zeki-g%C3%BClmez-088700180/)\n"
)
fig, ax = plt.subplots(figsize=(4, 4), dpi=300)
for i, x in enumerate([fx3, fx7]):
    ax.errorbar(
        x.estimate,
        i,
        xerr=[[x.estimate - x.lo90], [x.hi90 - x.estimate]],
        fmt="o",
        color=["#0072B2", "#D55E00"][i],
        capsize=4,
    )
ax.axvline(0, color=".5")
ax.set(
    yticks=[0, 1],
    yticklabels=["p=3", "p=7"],
    xlabel="Euro response: 100 log change",
    title="Common sample: proxy FX at month12",
)
fig.text(
    0.02,
    0.01,
    "Conditional90% bands;100bp tightening.\nApril2005–October2025;247 observations; no lag selection.",
    fontsize=7,
)
fig.tight_layout(rect=(0, 0.1, 1, 1))
fig.savefig(root / "figures/linkedin/headline.png", dpi=300)
plt.close(fig)
(root / "figures/linkedin/summary.txt").write_text(" ".join(findings) + "\n")
# Correct units and visible coverage on the annual accounting figure.
hd = pd.read_csv(res / "g3_history_annual.csv")
fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
for ax, area in zip(axes, ["EA_baseline", "TR_baseline"], strict=True):
    x = hd[hd.model == area]
    ax.plot(x.year, x.mean_inflation, label="Mean monthly inflation")
    ax.plot(x.year, x.mean_policy_contribution, label="Policy component")
    ax.fill_between(x.year, x.lo90, x.hi90, alpha=0.15)
    ax.set(
        title=f"{area}: recursive Cholesky, p={int(x.lag.iloc[0])}",
        ylabel="Annual average monthly log inflation, pp",
    )
    ax.legend(fontsize=8)
fig.text(
    0.02,
    0.01,
    "No annualisation. 2026: January–July (7 months). Every year coverage in CSV; samples/units in table metadata.",
    fontsize=8,
)
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(root / "figures/historical_decomposition.png", dpi=250)
fig.savefig(root / "figures/historical_decomposition.pdf")
plt.close(fig)
for name in [
    "g2_fevd",
    "g3_fevd",
    "g3_history_annual",
    "v3_methods_comparison",
    "v3_methods_status",
    "v3_granger_changes",
]:
    t = pd.read_csv(res / (name + ".csv"))
    (res / (name + ".md")).write_text(
        "\n".join(
            [
                "| " + " | ".join(t.columns) + " |",
                "| " + " | ".join(["---"] * len(t.columns)) + " |",
            ]
            + ["| " + " | ".join(map(str, x)) + " |" for x in t.itertuples(index=False, name=None)]
        )
        + "\n"
    )
(res / "policy_note_lineage.json").write_text(
    json.dumps(
        dict(
            inputs={
                n: hashlib.sha256((res / n).read_bytes()).hexdigest()
                for n in [
                    "v3_methods_comparison.csv",
                    "v3_methods_manifest.json",
                    "tr_identification_irfs.csv",
                    "g3_history_annual.csv",
                ]
            },
            render_only=True,
        ),
        indent=2,
    )
    + "\n"
)
print(json.dumps(findings))

# Publication-only reproduction description; estimator sources remain unchanged.
p = root / "README.md"
s = p.read_text()
start, end = s.index("## Reproduce"), s.index("## Technical notes")
p.write_text(
    s[:start]
    + "## Reproduce\n\n`make setup test lint quick` validates the implementations; `make policy-note report` rebuilds accepted V3 reports from included aggregate tables. Tectonic is required for the working paper; Python 3.11 and R (C1) for the full checks. See [reproduction notes](docs/REPRODUCTION.md) for the separate legacy empirical pipeline, free source access, credentials, and limits on reconstructing private V3 checkpoint histories. Data are acquired only through scripts and DATA.md; no raw observations are included. Original code is MIT.\n\n"
    + s[end:]
)
