# Technical working paper

`make report` generates numerical LaTeX tables and prose macros from the existing `results/` aggregates and compiles `main.tex` to `report/technical_report.pdf`. It performs no acquisition, model fitting, resampling or paid calls. `generated/lineage.json` binds each input by SHA-256 and records every empirical prose macro. Existing empirical figures are included unchanged.

The multi-file LaTeX project uses Tectonic 0.17.0 (XeTeX/LaTeX), with ordinary `\input` files. Install the official executable into this repository's `.tools/tectonic/tectonic`, put it on PATH, or run `TECTONIC=/absolute/path/tectonic make report`. Official releases: https://github.com/tectonic-typesetting/tectonic/releases/tag/tectonic%400.17.0 . Initial compilation downloads only required open-source TeX resources into Tectonic's local cache. No system-wide installation is required. After warming that cache, report builds use existing results without data-source/API credentials. Build logs and intermediates remain ignored in `.cache/technical/`.

Entry point: `main.tex`; common typography: `preamble.tex`; section prose: `paper.tex`; result-to-table mapping: `tables.py`; verified bibliography: `references.tex` and `references_verified.json`. Mathematical constants, variable/source IDs and bibliographic dates are definitions/metadata; empirical values are generated. Do not edit generated tables or numbers by hand.

This paper reports the empirical estimates only. Diagnostic outputs unavailable in the saved results are identified as unreported rather than recomputed. Raw observations, row-level predictions and private caches are never embedded. The short policy note remains a separate output, rebuilt with `make policy-note` when intentionally requested.

For a network-free rebuild after the TeX cache is warm, use `REPORT_OFFLINE=1 make report` (Tectonic only-cached mode). `PYTHON=/absolute/path/to/an/existing/venv/bin/python` can override the report interpreter when validating a source-only snapshot; no environment or credentials need to be copied into that snapshot. The input ledger also hashes every included empirical figure.
