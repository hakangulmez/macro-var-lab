# Euro area: a controlled methods comparison

How do monetary-response estimates for the euro area and Türkiye depend on the shock-identification scheme and response estimator?

We compare recursive VAR, sign-restricted VAR, recursive-shock local projections and proxy VAR on a common euro-area sample, April 2005 to October 2025. Within each of two fixed lag panels, p = 3 and p = 7, we hold variables, transformations, deterministic terms and shock size constant and trace a 100-basis-point tightening over 36 months. We use bootstrap bands for VAR responses, HAC bands for local projections and separately labelled sign-admissible ranges. We also compare three Türkiye specifications and interpret proxy estimates conditional on instrument validity.

![Headline](../figures/headline.png)

- The euro appreciates after a tightening: the proxy estimate at month 12 is 4.551 log percent with p = 3 (1.889, 7.630) and 3.305 with p = 7 (0.648, 5.505); both conditional 90% bands exclude zero.
- The price response is uncertain: proxy estimates at month 12 are 0.172 and -0.078 log percent, with both bands including zero. Estimates also change sign across methods.
- For Türkiye, the recursive price estimate at month 12 is -0.288 log percent. Recursive, FX-first and recursive-shock local-projection point estimates are negative, but their bands include zero.

![Türkiye price responses](../figures/tr_price_note.png)


## Limitations

- Proxy exogeneity is assumed; its bands condition on fitted dynamics.
- Sign-admissible ranges are not statistical confidence intervals.
- Both common-sample VARs have slightly unstable dynamics.
- Local projections have fewer supported origins at longer horizons.
- Latest-vintage observations do not reconstruct real-time information.

## Technical notes

Historical decompositions and FEVDs use recursive Cholesky identification, separately from the proxy comparison. Annual decomposition summaries are annual averages of monthly log inflation, not annual inflation; month counts and partial-year coverage are reported. Proxy conclusions depend on instrument exogeneity and conditional inference. The technical working paper gives complete equations, diagnostics and robustness results.

ECB and Eurostat; CBRT/EVDS and TURKSTAT; FRED; the Euro Area Monetary Policy Event-Study Database (EA-MPD).
