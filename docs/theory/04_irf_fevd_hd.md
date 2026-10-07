# Impulse responses, FEVD and historical decomposition

Status: draft for review

## Question and intuition

Impulse responses describe an identified disturbance's path. FEVD asks which identified shocks account for finite-horizon forecast errors. Historical decomposition reconstructs realised observations from past shocks plus initial and deterministic components. These objects answer different questions.

## Model and assumptions

$\Psi_0=I$, $\Psi_h=\sum_{j=1}^{\min(p,h)} A_j\Psi_{h-j}$. Structural IRFs are $\Psi_h B$. Shock shares at horizon H divide the sum of squared responses to one shock by the sum over all shocks and horizons below H. Historical contributions convolve realised innovations with the same moving-average coefficients.

## Interpretation and common errors

Finite-horizon FEVD shares sum to one across shocks even when long-run stationary variance does not exist. Do not extend that identity into a stationary infinite-horizon interpretation. An HD must reconstruct the data including its deterministic and initial-history terms; a chart omitting the latter is not an accounting check. If the VAR contains monthly inflation, summing its price response gives the price-level response. Differencing an HD in log prices gives its contribution to monthly inflation.

## Portfolio application

Bootstrap bands are pointwise unless a simultaneous construction is implemented. A full curve inside pointwise bands does not have the nominal joint coverage. Kilian bias correction estimates coefficient bias from bootstrap fits, reuses that estimate in the second stage, and shrinks corrections that would destabilize an initially stationary fit. An initially unstable fit is not forcibly made stationary. Plain residual bootstrap is retained separately; neither approach removes model misspecification.

```{=typst}
#pagebreak()
```

## Exam practice

### 1. Why does FEVD sum to one?

**Answer.** Every forecast-error component is assigned to the same complete orthogonal shock system.

### 2. What must HD reconstruct?

**Answer.** Observed outcomes from shock contributions plus deterministic and initial components.

### 3. How do inflation and price-level IRFs differ?

**Answer.** Inflation is the change; its cumulative response is the price-level response.

### 4. Are pointwise bands simultaneous?

**Answer.** No. Each horizon has its own marginal coverage statement.

### 5. Does stationarity correction fix every unstable model?

**Answer.** No. The original nonstationary branch remains unadjusted.

## Worked reasoning

Before interpreting an estimate, name the outcome unit, shock unit, identifying restrictions, sample and uncertainty method. If any is missing, the numerical sign alone does not support a causal claim. Separate a mechanical accounting identity from a maintained economic restriction. Explain how the answer would change under a different permissible identification without searching until a preferred answer appears. A correct exam response states what can and cannot be inferred, rather than merely naming a test or estimator.

## Reference and further reading

Verified primary reference: https://doi.org/10.1162/003465398557465

These notes are original explanations written for this portfolio; no thesis text or code was used.
