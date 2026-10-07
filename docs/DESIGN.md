# M1 G0 - Monetary transmission in the euro area and Türkiye

**7 October 2026 | G0/G1 approved; G2 awaiting review | Execution window: 7-17 October**

**Question.** How quickly does a 100-basis-point monetary tightening affect inflation, industrial activity and exchange rates, and how sensitive is the answer to identification?

**Series contract.** Monthly; exact selectors below. Eurostat keys follow dataset dimension order. EA uses constant-composition EA21, conditional on back-series coverage. `L` = 100 times log level; `R` = rate in percentage-point levels; `G` = 100 times monthly log difference, robustness only. Daily financial observations become arithmetic monthly means before transformation. NSA prices use month dummies; already seasonally/calendar-adjusted IP is not adjusted twice.

| Area / variable | Official source and exact ID / selector | Transform |
|:--|:--|:--|
| EA industrial production | Eurostat `sts_inpr_m`: `M.PRD.B-D.SCA.I21.EA21` | L |
| EA HICP headline / core | Eurostat `prc_hicp_minr`: `M.I25.TOTAL.EA21` / `M.I25.TOT_X_NRG_FOOD.EA21` | L |
| EA overnight rate | ECB `FM.M.U2.EUR.4F.MM.EONIA.HSTA` / `EST.B.EU000A2X2A25.WT` | R; EONIA through 2019-09, then €STR |
| EA two-year policy indicator | ECB `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y` | R; separate sample from 2004-09 |
| EA EUR/USD | FRED `DEXUSEU` (USD per EUR) | L; increase = EUR appreciation |
| TR industrial production | EVDS `TP.TSANAYMT2021.BCD` | L |
| TR CPI / core B / core C | EVDS `TP.TUKFIY2025.GENEL` / `TP.FE25.OKTG03` / `TP.FE25.OKTG04` | L; historical bridge below |
| TR funding-cost indicator | EVDS `TP.APIFON4` (AOFM) | R; use only its observed history |
| TR announced policy rate | CBRT **O/N Borrowing** / **1 Week Repo, Lending** tables (no verified EVDS ID) | R; effective-date daily steps, monthly means |
| TR USD/TRY / CPI-based REER | EVDS `TP.DK.USD.A.YTL` / `TP.RK.T1.Y` | L; also VECM |
| External Brent / VIX / US rate | FRED `DCOILBRENTEU` / `VIXCLS` / `FEDFUNDS` | L / log-level / R |
| TR two-/ten-year yields | Out of scope unless a permitted official source is verified at G1 | R if a permitted source is verified |

**Levels decision.** Baseline retains 100×log IP, prices, FX and REER, and percentage-point rate levels.
Possible unit roots do not trigger differencing; OLS levels-VAR estimation follows Sims–Stock–Watson (1990), with inference caveats.
Growth/differenced runs are robustness checks; unit-root/break diagnostics inform the separate VECM. Approved TR exception: fit levels first; if unstable or CPI is I(2)-compatible, use monthly inflation and retain the failed levels comparison. See G2_METHODS.md.

**Samples.** Targets: EA baseline 2004-09-2026-07 (ECB 2-year yield); overnight-rate robustness 1999-12-2019-12 (eleven earlier EA21 HICP months unavailable) (pre-ZLB-heavy comparison); TR target 2006-01-T, AOFM baseline only over its observed history; T = latest jointly observed complete month at G1, currently planned 2026-07. Fetch one preceding month for G. No interpolation. For pre-2026 TR prices, test the overlap bridge to `TP.GENENDEKS.T1`, `TP.FE.OKTG03`, `TP.FE.OKTG04`; rebasing must preserve growth and disclose classification changes. TR policy comparator uses O/N borrowing before 20 May 2010, then one-week repo; AOFM is the main effective-rate indicator where available. Approved TR baseline: 2011-01-2026-07 (AOFM); comparator robustness: 2006-01-2026-07. Non-overlapping regime checks: 2011-01-2018-05; 2018-06-2023-05; 2023-06-2026-07. The last regime uses four-variable LP only, no full VAR. Short regimes require parsimonious models, not a full seven-variable VAR.

**G1 extension check.** Bundesbank 2-year German zero-coupon terms/history verified; use only as a labelled 1999-12-2026-07 robustness indicator, with source attribution and author aggregation disclosed. TR 2y/10y yields are nonblocking and otherwise excluded.

**Identification and checks.** ADF/KPSS/PP and Zivot-Andrews; diagnostics only, never an automatic baseline differencing rule. AIC/BIC/HQ over 1-12 lags, BIC baseline, stability, residual LM/normality and Granger diagnostics. Recursive order: external block, activity, headline inflation, policy indicator, FX; TR external equations exclude domestic current/lagged feedback. Core replaces headline in robustness runs. Bootstrap 68/90% IRFs to 36 months, FEVD and inflation historical decomposition. Compare sign restrictions (rate positive; cumulative price response nonpositive, months 0-3; activity/FX unrestricted); accepted-draw spread is not a confidence interval. LP uses the same identified shocks/controls and Newey-West HAC lag h+1; joint bootstrap propagates shock-estimation uncertainty. Johansen/VECM only for empirically I(1) log CPI/FX/REER. Optional EA proxy-SVAR: monthly EA-MPD surprises, only after workbook-column, reuse-rights and instrument-strength checks. No raw dataset redistribution.

**Outputs / risks.** EA/TR IRF panels, FEVD, inflation decomposition, LP-versus-VAR, two-page `report/policy_note.pdf`, ten theory notes and LinkedIn figure; tables generated from code, PNG 300 dpi + PDF. Risks: ZLB, rate-splice discontinuity, regime instability, seasonal/rebasing breaks, small samples, EA21 history, missing TR yields, VIX/EA-MPD reuse limits and instrument information effects. G1 must verify coverage/terms and report gaps; no silent substitutions. No paid APIs or thesis reuse. **G1:** report data checks and source gaps, stop if blocked. Priority: data → recursive SVAR + LP → signs → TR VECM → optional proxy; theory notes after G2. Source links and verification detail: [DATA.md](../DATA.md).
