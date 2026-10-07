# M1 sources, rights and data contract — 7 October 2026

G3 approved for publication. The following retains the dated G1 source contract: all ten EVDS and four FRED streams verified. Final identification results are in the policy note and aggregate tables. MIT covers original code only; source data and populated `.env` stay local/gitignored. The measured source contract below preserves coverage gaps and failed core bridge checks.

## Eurostat

- [IP structure metadata](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/STS_INPR_M/1.0?references=descendants&detail=referencepartial):
  verified order `freq, indic_bt, nace_r2, s_adj, unit, geo`; selector
  `M.PRD.B-D.SCA.I21.EA21`.
- [HICP structure metadata](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/PRC_HICP_MINR/1.0?references=descendants&detail=referencepartial):
  verified order `freq, unit, coicop18, geo`; headline `M.I25.TOTAL.EA21`, core
  `M.I25.TOT_X_NRG_FOOD.EA21` (excluding energy, food, alcohol and tobacco).
- [2026 HICP changes](https://ec.europa.eu/eurostat/web/hicp/information-data):
  use `prc_hicp_minr`, ECOICOP version 2; `prc_hicp_midx` is discontinued.
  EA21 is a constant 21-country aggregate including Bulgaria. G1 must verify
  full history; do not silently mix fixed and changing composition.
- [Latest IP release checked](https://ec.europa.eu/eurostat/web/products-euro-indicators/w/4-16092026-ap):
  July 2026, next release 15 October. July is the observed and fixed baseline endpoint at G1.

## ECB

- [Monthly EONIA](https://data.ecb.europa.eu/data/datasets/FM/FM.M.U2.EUR.4F.MM.EONIA.HSTA):
  `FM.M.U2.EUR.4F.MM.EONIA.HSTA`.
- [Daily €STR](https://data.ecb.europa.eu/data/datasets/EST/EST.B.EU000A2X2A25.WT):
  `EST.B.EU000A2X2A25.WT`, starts 1 October 2019.
- [AAA two-year spot yield](https://data.ecb.europa.eu/data/datasets/YC/YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y):
  `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y`, starts 6 September 2004. This is a
  fitted government-bond yield, not OIS or an observed policy rate. Compare
  yield/overnight specifications on a common sample; no manufactured prehistory.
- G1 verified EONIA methodology and documented reuse rights. Add a
  transition control and compare a spread-adjusted splice: the overnight
  definition change must not become an identified monetary shock.

## Türkiye: EVDS 3 public catalogue

Official [EVDS 3](https://evds3.tcmb.gov.tr/) metadata endpoints inspected:
`/igmevdsms-dis/searchResults?searchVal=...` and
`/igmevdsms-dis/serieList/fe/type=json&code=...`. G0 used public metadata only; G1 now verifies authenticated catalogue and observations. Verified codes:

| Variable | Data group | Series |
|:--|:--|:--|
| IP, total industry, seasonal/calendar adjusted | `bie_tsanaymt2021` | `TP.TSANAYMT2021.BCD` |
| General CPI, 2025=100 | `bie_tukfiy2025` | `TP.TUKFIY2025.GENEL` |
| Core B / C, 2025=100 | `bie_oktug2025` | `TP.FE25.OKTG03` / `TP.FE25.OKTG04` |
| General CPI, 2003=100 | `bie_tukfiy2003` | `TP.GENENDEKS.T1` |
| Historical core B / C, archive | `bie_feoktg` | `TP.FE.OKTG03` / `TP.FE.OKTG04` |
| Weighted average funding cost | `bie_apifon` | `TP.APIFON4` |
| USD FX buying rate, not banknotes | catalogue search | `TP.DK.USD.A.YTL` |
| CPI-based REER, 2025=100 | `bie_rktufey` | `TP.RK.T1.Y` |

Core B excludes unprocessed food, energy, alcohol/tobacco and gold; C also
excludes processed food/nonalcoholic beverages. Replace headline with each core
outcome in robustness models. Check historical overlap before rebasing; preserve
growth and document classification changes. Do not splice by index equality.

The G0 date-range route failed; the documented authenticated series-list route at G1 supplies start/end dates. AOFM starts 3 January 2011; its baseline uses only that observed history.
The public category catalogue and searches did not establish policy-rate or
two-/ten-year government-yield EVDS IDs. This is an unresolved source gap, not
proof of nonexistence. No loan/deposit-rate, debt-stock, auction-cost or commercial
scraping substitute. Yield extensions stay unavailable pending a permitted free source.

### Announced-rate table identifiers

- [CBRT O/N](https://tcmb.gov.tr/wps/wcm/connect/EN/TCMB%2BEN/Main%2BMenu/Core%2BFunctions/Monetary%2BPolicy/Central%2BBank%2BInterest%2BRates/CBRT%2BINTEREST%2BRATES):
  title `CBRT Interest Rates (%) Overnight (O/N)`, `Borrowing` column before
  20 May 2010. Table identifiers are not asserted EVDS IDs.
- [One-week repo](https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB%2BEN/Main%2BMenu/Core%2BFunctions/Monetary%2BPolicy/Central%2BBank%2BInterest%2BRates/1%2BWeek%2BRepo):
  title `1 Week Repo`, `Lending` column, effective dates from 20 May 2010.
  Daily rate steps persist until the next change; this is the announced schedule,
  not interpolation of missing macro observations.
- [2018 simplification](https://www.tcmb.gov.tr/wps/wcm/connect/en/tcmb%2Ben/main%2Bmenu/announcements/press%2Breleases/2018/ano2018-21):
  effective 1 June 2018. Regime partitions in DESIGN are descriptive, not assumed
  homogeneous. June 2023 straddles the rate change; exclude transition months as
  a robustness check. Small regimes need lag/parsimony limits before estimation.
- [2026 MPC summary](https://www.tcmb.gov.tr/wps/wcm/connect/tr/tcmb%2Btr/main%2Bmenu/duyurular/basin/2026/duy2026-14)
  documents announced/effective-rate divergence outside the old corridor years.
  Compare AOFM with announced-rate specifications wherever both are observed.

## FRED and optional EA-MPD

- [DEXUSEU](https://fred.stlouisfed.org/series/DEXUSEU): Federal Reserve daily USD
  per EUR; public domain, attribution requested.
- [DCOILBRENTEU](https://fred.stlouisfed.org/series/DCOILBRENTEU): EIA daily Brent
  USD/barrel; public domain, attribution requested.
- [VIXCLS](https://fred.stlouisfed.org/series/VIXCLS): CBOE daily close;
  copyrighted, citation required. Check publication rights; no raw redistribution.
- [FEDFUNDS](https://fred.stlouisfed.org/series/FEDFUNDS): monthly effective Fed
  rate in percent, TR external block.
- [Altavilla et al., ECB Working Paper 2281](https://www.ecb.europa.eu/pub/pdf/scpwps/ecb.wp2281~3303fd281b.en.pdf)
  describes EA-MPD; the official asset is `Dataset_EA-MPD.xlsx` in the ECB annex
  directory. At G1 the workbook had not yet been downloaded; the overnight source update below records its later admission. [ECB reuse conditions](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html)
  require attribution/transformation disclosure and have exceptions for authored
  documents; underlying data rights require a separate check. Activate proxy-SVAR
  only after workbook notices, exact column/window definitions and strength are
  checked. Aggregate disjoint event windows monthly, without double-counting
  combined/press-release/conference surprises; report information-effect risks.

## Source and privacy contract

G1 must log source URL, access date, terms/rate limits, units, adjustment,
coverage/missingness, original-provider rights, transformations, SHA-256 and
retrieval failures. Credentials are user-supplied, sent only in official HTTPS authentication fields, and never retained in exception output, logs, saved URLs or manifests. No paid APIs or raw data in Git.


## Current G1 snapshot

7 October 2026, run `g1_20261007T005036+0200`; machine contract `configs/data.yaml`, seed 20261007. Retrieval December 1998–September 2026; **EA baseline September 2004–July 2026 fixed**, 263 complete months. Approved robustness starts December 1999: eleven earlier HICP months unavailable; overnight comparison ends December 2019, Bundesbank extension July 2026. Bundesbank is only a labelled German-yield robustness indicator. TR AOFM baseline January 2011–July 2026, 187 months; 60 earlier target months lack AOFM. No substitution.

| Series | First in target | Last in target | Observed months | Missing target months |
|:--|:--|:--|--:|--:|
| ea_ip | 1999-01 | 2026-07 | 331 | 2 |
| ea_hicp | 1999-12 | 2026-09 | 322 | 11 |
| ea_core | 1999-12 | 2026-09 | 322 | 11 |
| ea_2y | 2004-09 | 2026-09 | 265 | 68 |
| ea_eonia | 1999-01 | 2021-12 | 276 | 57 |
| ea_estr | 2019-10 | 2026-09 | 84 | 249 |
| de_2y | 1999-01 | 2026-09 | 333 | 0 |
| eurusd | 1999-01 | 2026-09 | 333 | 0 |
| brent | 1999-01 | 2026-09 | 333 | 0 |
| vix | 1999-01 | 2026-09 | 333 | 0 |
| fedfunds | 1999-01 | 2026-09 | 333 | 0 |
| tr_ip | 2006-01 | 2026-07 | 247 | 2 |
| tr_cpi | 2006-01 | 2026-09 | 249 | 0 |
| tr_core_b | 2006-01 | 2026-09 | 249 | 0 |
| tr_core_c | 2006-01 | 2026-09 | 249 | 0 |
| tr_cpi_old | 2006-01 | 2026-09 | 249 | 0 |
| tr_core_b_old | 2006-01 | 2025-12 | 240 | 9 |
| tr_core_c_old | 2006-01 | 2025-12 | 240 | 9 |
| tr_aofm | 2011-01 | 2026-09 | 189 | 60 |
| usdtry | 2006-01 | 2026-09 | 249 | 0 |
| tr_reer | 2006-01 | 2026-09 | 249 | 0 |
| tr_announced | 2006-01 | 2026-09 | 249 | 0 |

### Verified EVDS identity, units and full catalogue coverage

| EVDS ID | Native frequency | Unit | Catalogue full coverage (day-month-year) | Observed within retrieval window |
|:--|:--|:--|:--|:--|
| `TP.TSANAYMT2021.BCD` | monthly | index 2021=100 | 01-01-1986–01-07-2026 | 1998-12–2026-07 |
| `TP.TUKFIY2025.GENEL` | monthly | index 2025=100 | 01-01-2005–01-09-2026 | 2005-01–2026-09 |
| `TP.FE25.OKTG03` | monthly | index 2025=100 | 01-01-2005–01-09-2026 | 2005-01–2026-09 |
| `TP.FE25.OKTG04` | monthly | index 2025=100 | 01-01-2005–01-09-2026 | 2005-01–2026-09 |
| `TP.GENENDEKS.T1` | monthly | index 2003=100 | 01-01-2003–01-09-2026 | 2003-01–2026-09 |
| `TP.FE.OKTG03` | monthly | index 2003=100 | 01-01-2003–01-12-2025 | 2003-01–2025-12 |
| `TP.FE.OKTG04` | monthly | index 2003=100 | 01-01-2003–01-12-2025 | 2003-01–2025-12 |
| `TP.APIFON4` | business_daily | percent | 03-01-2011–06-10-2026 | 2011-01-03–2026-09-30 |
| `TP.DK.USD.A.YTL` | daily | TRY per USD, foreign-exchange buying | 02-01-1950–07-10-2026 | 1998-12-01–2026-09-30 |
| `TP.RK.T1.Y` | monthly | index 2025=100 | 01-01-1994–01-09-2026 | 1998-12–2026-09 |

`results/evds_metadata.json` includes official source/group metadata and SHA references. [Service guide](https://evds3.tcmb.gov.tr/igmevdsms-dis/documents/showDocument?docId=16): header key, native levels/frequencies by default, source daily updates, 1,000-row backward cap. Daily requests are split into nonoverlapping two-calendar-year windows and reject saturation; monthly requests remain below the cap. Full catalogue start dates distinguish native source history from the retrieval window. AOFM group combines funding amounts and a percentage rate: `TP.APIFON4` is the rate. USDTRY is FX buying, TRY per USD; REER increase is appreciation.

Current price histories begin January 2005 and cover the full target. Headline bridge passes fixed 0.2% ratio tolerance; core B/C fail. No splices or threshold change. Historical archives are diagnostics only. [TURKSTAT methodological announcement](https://www.tuik.gov.tr/media/announcements/TUFE_Duyuru30102025.pdf) documents 2026 rebasing/ECOICOP v2/weight-source changes and regrouped histories. Source classification change is retained, not erased by scaling. `results/price_bridge_detail.json` also reports growth differences. CBRT announced comparator uses calendar-day effective-date holds; AOFM uses observed-day arithmetic means; no main indicator substitution. Full definitions and aggregate comparison: `results/policy_comparator_check.json`.

### Transformations and preservation

100×log IP/prices/FX/REER/Brent, unscaled log VIX; rate percentage-point levels. Aggregate observed daily values before logs. First differences are a separate robustness file, rates included as first differences, with full-month reindexing before differences. No interpolation, outlier removal or repeated seasonal adjustment. NSA price month dummies and policy-transition sensitivity are deferred to G2. Data QA plots are private descriptive checks, not IRFs. Revised histories are not real-time vintages. Archived cores end December 2025; unreleased IP tails and pre-AOFM history remain missing. Earlier broad/truncated EVDS responses and manifests are retained; final bounded-window samples supersede them for G1.

### FRED API, fallback, terms and attribution

Default `fred_route: api`: official **v1 `fred/series/observations`**, local FRED_API_KEY, JSON, explicit bounds and 100,000-row pagination guard; all four streams succeeded. [Documentation](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html), [legal terms](https://fred.stlouisfed.org/legal/), [privacy](https://www.stlouisfed.org/privacy-policy). Required notice:

**This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.**

Federal Reserve Board via FRED (DEXUSEU/FEDFUNDS), U.S. EIA via FRED (DCOILBRENTEU), CBOE via FRED (VIXCLS). Acknowledge original providers and FRED; API access does not override third-party copyright. VIX remains copyrighted, retained for private noncommercial research; no raw redistribution. Terms prohibit AI/ML training and wholesale downloading; M1 uses four pinned series for conventional statistical research, no AI/ML training. Every user supplies their own key and is subject to linked terms. No credentials or personal-user data collected beyond reading the local keys for authentication.

**Public CSV fallback:** explicitly change `fred_route` to `public_csv` for the same IDs only if permitted and needed, rerun with a newly recorded manifest. No automatic fallback on auth/API failures. [Official download help](https://fred.stlouisfed.org/help/data/downloading/using-the-download-data-link/). Preserve previous route's source evidence and report changed access date/route; do not silently merge snapshots.

### Other terms and source evidence

Source documents (HTTP status, URL, true access date, bytes, SHA) are archived privately; `results/terms_register.json` records evidence without raw content. [Eurostat](https://ec.europa.eu/eurostat/help/copyright-notice): source acknowledgement, disclose author's transformations; Eurostat is not responsible for the author's calculations. [ECB](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html): attribution/calculation disclosure, authored/third-party exceptions. [Bundesbank](https://www.bundesbank.de/en/homepage/user-information/conditions-for-the-general-use-of-the-website-764706): attributed personal/professional source-information use, preserve originals; label **Source: Deutsche Bundesbank; monthly averages and transformations: author**. Do not borrow website images or imply altered observations are official. [EVDS](https://evds3.tcmb.gov.tr/igmevdsms-dis/documents/showDocument?docId=21): reference CBRT and original provider, unofficial English translation, no charging for source data. [CBRT](https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB%2BEN/Bottom%2BMenu/Other/Disclaimer): terms for announced tables; commercial reuse requires its permission. Private research admission does not establish commercial publication rights. No paid feeds, invented TR yields, raw publication, thesis/course reuse or prohibited ATS sources. EA-MPD was deferred at G1 and admitted during the approved overnight run; see the dated source update below.

### Reproduction, credentials and read-only audit

`make verify-metadata`, `make data`, `make checks` (offline/native), `make audit` (read-only inputs; only aggregate audit result written), `make quick` (isolated synthetic, keyless/offline), `make lint test`. Exit 2 means genuinely unavailable required data/joint sample, not a successful gate. Original response caches are immutable and checksum-verified; current re-execution does not refresh their acquisition dates. Revised release snapshots require explicit new acquisition evidence. Sequential starts ≥1.05s, 30 MB cap, no hidden retries, source-daily caching, no auth redirects.

Literal `.env` parsing executes no code. EVDS header/FRED query credentials travel only to official HTTPS hosts and are omitted from saved URLs, cache identity, logs and manifests. Credential-echoing responses are refused. Actual-key byte scanning and Git exclusions independently checked; no printed values. All execution, environments, caches, native/processed files and run snapshots remain local, never executed from Drive. `data/`, `.env`, `runs/`, `.venv/` excluded from Git. Public release includes code, documentation and aggregate author estimates only.

The historical G1 audit recorded `433` passed / `0` failed, zero network calls; its private audit records are not distributed. `results/g1_audit.json` checks raw→native→monthly→levels/differences lineage, policy-calendar weights, missingness/sample contracts, metadata identity/frequency/units provenance, hashes/snapshots and credential safety. The historical G1 review report is retained privately; this DATA.md records its source limitations. G1 approved; the G2 review decisions are applied in the overnight release. G3 is approved; see report/policy_note.pdf for the final findings.

### G2 core bridge check and statistical transformations

No core splice: B ratio range **0.200031%**, C **0.207526%**, both exceeding the predeclared **0.2% ratio-range tolerance**. The B failure is marginal, retained without rounding the gate. Maximum paired monthly log-growth gaps: B **0.199831 pp**, C **0.146075 pp**; the ratio criterion and growth-gap statistic are distinct. Old/current growth comparison is generated in private `runs/<G2 analysis_id>/core_growth_overlap.png` (PDF companion); full overlap February 2005-December 2025 after taking consecutive differences. Current-base histories alone cover all G2 target months. See `results/g2_artifacts.json` for the exact path/hash; no source-derived row-level check is committed.

TR levels instability triggers the approved monthly-inflation baseline; preserved levels results remain labelled. EA remains levels. G2 growth robustness differences log variables but **keeps rates in percentage-point levels**; it does not use G1's generic all-column difference file. Model transformations, regime windows, conditional I(1) gate, bootstrap assumptions and inference limitations are specified in `docs/G2_METHODS.md`. Public results contain author estimates/aggregate diagnostics; observed inflation history, source-derived paired growth, residuals and identified shocks remain private. G2 is offline and retains G1 source/licence attribution; no new source access or paid calls.


## Overnight EA-MPD source and reproduction

EA-MPD is obtained at runtime from https://www.ecb.europa.eu/pub/pdf/annex/Dataset_EA-MPD.xlsx, private only. ECB attribution and modification-disclosure terms: https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html. Cite Altavilla et al. (2019), DOI 10.1016/j.jmoneco.2019.08.016. Monetary Event Window OIS_2Y is in basis points; monthly sums are formed only inside the observed January 1999–October 2025 history; later periods remain unavailable. September 2004–October 2025 proxy overlap differs from the main September 2004–July 2026 sample (effective regression start is after initial lags). Workbook checksum and sample are stored in results/g3_summary.json. Mixed Excel dates and dd/mm/yyyy strings are parsed explicitly. No raw workbook or row-level series in Git.

`make all` now acquires missing official G1 inputs using local .env and performs data checks before estimation. Repeated runs use private caches. The clean-clone test starts with only .env and runtime-installed dependencies; see results/reproduction_check.json for measured outcome. Keys are never printed.

EA-MPD downloaded 7 October 2026. Workbook SHA-256 `f417fb861a305e3cbb871a7571c4899ba6bca003d9e087024d2f3f0744426cef`. Combined Monetary Event Window, OIS_2Y; no missing surprise cells inside the September 2004–October 2025 baseline overlap. Monthly non-event zeros are restricted to covered months. Private workbook retained outside Git.


## V2 resolution, 7 October 2026

Fresh-clone ECB acquisition is now resolved: retry public ECB transient/network errors at most five times (1,2,4,8 seconds), clear endpoint/status on exhaustion. make setup all succeeded from a new local clone with only .env. Processed numeric values/missing masks are identical; aggregate IRF/FEVD/history output CSVs are byte-identical to the approved local results. See results/reproduction_check.json. Preferred EA proxy subject to F>10 relevance and untested exclusion, 2004-09 to2025-10; explicit price/IP/FX 0-36-month bands. TR estimates retained unchanged.


## Public snapshot and runtime files

Only code, original documentation, generated figures and aggregate estimates are distributed. References above to metadata, terms registers, source checksums, raw/processed panels and run paths describe private runtime outputs; these are not bundled. `make setup all` acquires data with the reader's own FRED/EVDS keys. `make verify-metadata` creates catalogue metadata locally, and `make audit` verifies runtime G1 lineage. Review-report generators and local acceptance logs/history are excluded. The sanitized reproduction record contains only hashes, aggregate checks and timing; the pre-retry access-code snapshot preserves the verifiable acquisition-only transition without publishing private Git history. See docs/REPRODUCTION.md.
