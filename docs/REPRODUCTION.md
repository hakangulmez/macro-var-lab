# Reproduction of the accepted V3 snapshot

The checked-in aggregate tables and reports are the accepted, frozen V3 results. Source data, fitted objects, row-level forecasts, bootstrap arrays and repetition-level simulation draws are excluded. Data access and attribution remain in DATA.md; MIT applies to original code, not source data.

## Rebuild and tests from a clean clone

Install Python 3.11, uv and R for C1. `make setup test lint quick` installs only repository-local dependencies and checks implementations with synthetic fixtures; the R test uses its own temporary 100-repetition fixture, not another V3 precision run. Install Tectonic locally or set `TECTONIC=/path/to/tectonic`; `make policy-note report` rebuilds the current notes and working paper from included aggregate tables, with no data download, refitting or credentials. Working-paper equations are tied to implementation hashes. The supplied frozen V2 aggregate fixtures support regression tests and comparisons; they contain no private rows or history.

## Acquisition and empirical reruns

`make all` remains the original pre-V3 empirical reproduction pipeline. M1 acquires official sources with the reader's own ignored `.env` (FRED_API_KEY, EVDS_API_KEY); C1 fetches the public SIPP extract and did example for permitted private analysis. It writes private data/runs and replaces aggregate outputs in that working checkout. It is not an exact reconstruction of the approved V3 private-artifact history: new source vintages may differ, and the original 1,000-repetition continuation reused private repetition-level checkpoints. Run it in a separate clone; do not describe its legacy 100-repetition results as V3. Archive the supplied aggregates before any empirical rerun.

V3 methods and diagnostic source code is included. M1 `make v3-methods` requires a locally acquired panel and the exact, permitted EA-MPD workbook with the documented frozen hash; a refreshed workbook is not silently substituted. `make v3-diagnostics` in C1 requires runtime SIPP data; balanced influence-function checks require the local fitted did object. The consumed MC manifests intentionally prevent an accidental second precision budget. Reconstructing those private checkpoint histories is outside the self-contained aggregate report build; no private checkpoints are redistributed. V3 protocols retain all specifications, dates, availability assumptions, seeds and fixed budgets.

The public code/figures/aggregate results were synchronized from approved local source commits, not by merging private research Git history. Publication metadata explains small documentation-only differences. No learner, instrument, lag search or causal estimand was changed for publication.
