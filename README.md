# macro-var-lab

How do monetary-response estimates for the euro area and Türkiye depend on the shock-identification scheme and response estimator?

![Headline](figures/headline.png)

## Findings

- The euro appreciates after a tightening: the proxy estimate at month 12 is 4.551 log percent with p = 3 (1.889, 7.630) and 3.305 with p = 7 (0.648, 5.505); both conditional 90% bands exclude zero.
- The price response is uncertain: proxy estimates at month 12 are 0.172 and -0.078 log percent, with both bands including zero. Estimates also change sign across methods.
- For Türkiye, the recursive price estimate at month 12 is -0.288 log percent. Recursive, FX-first and recursive-shock local-projection point estimates are negative, but their bands include zero.

## Method

We compare recursive VAR, sign-restricted VAR, recursive-shock local projections and proxy VAR on a common euro-area sample, April 2005 to October 2025. Within each of two fixed lag panels, p = 3 and p = 7, we hold variables, transformations, deterministic terms and shock size constant and trace a 100-basis-point tightening over 36 months. We use bootstrap bands for VAR responses, HAC bands for local projections and separately labelled sign-admissible ranges. We also compare three Türkiye specifications and interpret proxy estimates conditional on instrument validity.

## Data sources

ECB yields, Eurostat production/prices, CBRT/EVDS and TURKSTAT Türkiye series, FRED global controls, and EA-MPD policy-event surprises. [DATA.md](DATA.md) lists exact IDs, transformations, attribution and terms. Source observations are acquired through scripts and are not redistributed.

## How to reproduce

Requirements: Python 3.11, uv and Tectonic. Dependencies install inside the repository.

```sh
make setup
make test lint quick
make policy-note report
```

The last command rebuilds the notes and working paper from included aggregate results, without data acquisition or model fitting. `make quick` is offline and synthetic. Empirical acquisition/rerun commands, required credentials and source-vintage constraints are documented in [provenance and reproduction](docs/PROVENANCE.md).

## Reports

[Two-page policy note](report/policy_note.pdf) · [Technical working paper](report/technical_report.pdf) · [Detailed results](report/report.md)

## Limitations

- Proxy exogeneity is assumed; its bands condition on fitted dynamics.
- Sign-admissible ranges are not statistical confidence intervals.
- Both common-sample VARs have slightly unstable dynamics.
- Local projections have fewer supported origins at longer horizons.
- Latest-vintage observations do not reconstruct real-time information.

## Licence

Original code: [MIT](LICENSE). Third-party data retain their source terms and are not included.

Hakan Zeki Gülmez · [GitHub](https://github.com/hakangulmez) · [LinkedIn](https://www.linkedin.com/in/hakan-zeki-g%C3%BClmez-088700180/)
