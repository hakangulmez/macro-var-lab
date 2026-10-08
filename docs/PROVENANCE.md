# Provenance and reproduction

The concise README presents the empirical question and results. This document retains the research protocols, result lineage, version history, reproduction boundaries and Monte Carlo replay details. Source data remain governed by DATA.md.

# Reproduction of the accepted V3 snapshot

The checked-in aggregate tables and reports are the accepted, frozen V3 results. Source data, fitted objects, row-level forecasts, bootstrap arrays and repetition-level simulation draws are excluded. Data access and attribution remain in DATA.md; MIT applies to original code, not source data.

## Rebuild and tests from a clean clone

Install Python 3.11, uv and R for C1. `make setup test lint quick` installs only repository-local dependencies and checks implementations with synthetic fixtures; the R test uses its own temporary 100-repetition fixture, not another V3 precision run. Install Tectonic locally or set `TECTONIC=/path/to/tectonic`; `make policy-note report` rebuilds the current notes and working paper from included aggregate tables, with no data download, refitting or credentials. Working-paper equations are tied to implementation hashes. The supplied frozen V2 aggregate fixtures support regression tests and comparisons; they contain no private rows or history.

## Acquisition and empirical reruns

`make all` remains the original pre-V3 empirical reproduction pipeline. M1 acquires official sources with the reader's own ignored `.env` (FRED_API_KEY, EVDS_API_KEY); C1 fetches the public SIPP extract and did example for permitted private analysis. It writes private data/runs and replaces aggregate outputs in that working checkout. It is not an exact reconstruction of the approved V3 private-artifact history: new source vintages may differ, and the original 1,000-repetition continuation reused private repetition-level checkpoints. Run it in a separate clone; do not describe its legacy 100-repetition results as V3. Archive the supplied aggregates before any empirical rerun.

V3 methods and diagnostic source code is included. M1 `make v3-methods` requires a locally acquired panel and the exact, permitted EA-MPD workbook with the documented frozen hash; a refreshed workbook is not silently substituted. `make v3-diagnostics` in C1 requires runtime SIPP data; balanced influence-function checks require the local fitted did object. The consumed MC manifests intentionally prevent an accidental second precision budget. Reconstructing those private checkpoint histories is outside the self-contained aggregate report build; no private checkpoints are redistributed. V3 protocols retain all specifications, dates, availability assumptions, seeds and fixed budgets.

The public code/figures/aggregate results were synchronized from approved local source commits, not by merging private research Git history. Publication metadata explains small documentation-only differences. No learner, instrument, lag search or causal estimand was changed for publication.


## Research lineage and detailed disclosures

V3 methods comparison on a common sample and lag specification: April 2005–October 2025,247 usable VAR observations for both p3 and p7; September 2004–March 2005 supplies lag history only. The user authorized this mechanical start adjustment before comparison results because the frozen yield starts September 2004. All original frozen inputs remain unchanged. Six variables, existing transforms, intercept/month indicators,100 bp shock and36-month horizons fixed within each panel. Response estimators differ: recursive-shock LP uses the recursive innovation and VAR-design/ordered-predecessor controls, with horizon-specific supported origins247−h (235 at h12). It is not an identification-only contrast.

Proxy instrument remains combined EA-MPD Monetary Event Window/OIS_2Y. First-stage F p3=19.597947, p7=18.826251; both exceed the unchanged 10 threshold. Exogeneity is not established. Conditional paired block 6 inference fixes VAR propagation slopes and omits weak draws: p3 accepted407/499, p7 accepted379/499. This is not weak-IV-robust/full-chain inference. Recursive iid Kilian bias200/outer499, original sign restrictions1000 admissible rotations, existing LP HAC remain. Sign medians/ranges may lie beyond figure limits; full ranges are in CSV. Neither lag was selected by narrative or significance. Spectral radii p3=1.000726, p7=1.003395 exceed one; unstable dynamics remain visible.

Inherited TR IRFs, regimes, transformations and original alternatives are unchanged. The policy-column bug is fixed by labels.index('policy'), with invariant reorder tests and only affected Granger entries regenerated. Historical accounting remains inherited recursive Cholesky, not proxy accounting. FEVD fractions describe native outcomes (EA price levels; TR monthly inflation), unnormalized unit-variance shocks; exported tables name sample, lag and units. HD reports arithmetic annual averages of monthly100ΔlogP in percentage points, NOT annual/cumulative inflation. Native TR inflation uses the same scale. Coverage and number of months appear for every year; 2026 contains January–July, seven months, without annualisation. Components reconcile with represented levels/monthly inflation, with checks in v3_hd_accounting.json. This descriptive decomposition is not a structural explanation of each episode or a policy counterfactual.

New V3 methods outputs are distinct from inherited g3_irfs/ea_proxy_irfs and original full-window accounting. The private archive retains original V2 hashes; only required frozen aggregate regression fixtures are included publicly. Protocol, source workbook, processed data and private bootstrap lineage are recorded in V3 manifests. No raw data, private shocks or fitted objects are committed.


## Limitations and future work

Instrument exogeneity/information-shock separation and alternative event windows; serial-dependence-robust strength tests and weak-IV/full-estimation-chain bands; persistence-robust LP; shrinkage, dimension and break diagnostics; TR intervention/indicator/regime comparability; sign-rotation and restriction-duration sensitivity; economically interpretable counterfactual policy paths. These substantive review extensions are deferred.

Hakan Zeki Gülmez | [GitHub](https://github.com/hakangulmez) | [LinkedIn](https://www.linkedin.com/in/hakan-zeki-g%C3%BClmez-088700180/)
