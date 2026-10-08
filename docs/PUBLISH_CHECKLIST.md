# V3 public synchronization checklist — 8 October 2026

Owner authorized synchronization of accepted V3 to this existing public main branch, without force-push. No other repositories or private histories are authorized. Exact public allowlist: PUBLIC_FILES.txt; source/aggregate provenance: PUBLIC_V3_PROVENANCE.json.

- [x] Allowlisted code, tests, documentation, figures, aggregate results and report sources/PDFs only; no data/ directory, .env, private caches, model objects, databases, environments or thesis material.
- [x] Existing MIT code licence retained; separate source licences and runtime acquisition in DATA.md.
- [x] Exact-key and offline heuristic file/history scans; private-path exclusion probes.
- [x] Fresh clone setup/build/test/lint/quick and scientific source acquisition checks.
- Publication procedure: fast-forward push main only, then verify the live remote tree, README, headline and PDF links; the dated external publication report records the resulting commit hashes.

No private research commits are merged. Existing public history is retained. Final executed verification is recorded in docs/PUBLICATION_VALIDATION.json.
