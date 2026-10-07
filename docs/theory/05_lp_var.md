# Local projections versus VAR

Status: draft for review

## Question and intuition

Local projections estimate a separate regression for each horizon rather than repeatedly applying a single fitted transition equation. This permits horizon-specific dynamics but can increase sampling variance. Neither method supplies identification by itself: the shock and control assumptions must still be credible.

## Model and assumptions

$y_{t+h}=a_h+\theta_h z_t+\Gamma_h X_t+e_{t+h}$. Here $z_t$ is an identified policy innovation in rate units. Overlapping dependent outcomes induce horizon-dependent residual dependence. Newey-West HAC with a reported bandwidth estimates the long-run covariance of the regression score.

## Interpretation and common errors

A VAR borrows structure across horizons. LP trades those restrictions for flexibility. In small monthly samples, high-dimensional controls can exhaust the degrees of freedom at long horizons; the correct result is unavailable inference, not extrapolation. An LP using a point-estimated VAR shock is conditional on that shock; a joint bootstrap can propagate shock-estimation uncertainty, while ordinary HAC does not.

## Portfolio application

For cumulative inflation, construct the cumulative dependent outcome before fitting the regression and estimating HAC. Summing standard errors across horizons is invalid because their estimates are correlated. Pre-shock price levels enter as nuisance controls. The pass-through LP is normalized to a TRY depreciation normalized to 100 times log(1.10), exactly a ten percent increase in TRY per USD. The recent TR regime has only four domestic variables and one lag, with unavailable long horizons left missing.

```{=typst}
#pagebreak()
```

## Exam practice

### 1. Why estimate each horizon separately?

**Answer.** To avoid imposing one VAR transition equation on all response horizons.

### 2. Why use HAC?

**Answer.** Overlapping outcomes and serial dependence correlate the regression scores.

### 3. Can LP fix an invalid policy shock?

**Answer.** No. Identification remains a separate assumption.

### 4. How should cumulative-response uncertainty be computed?

**Answer.** Estimate a cumulative dependent outcome directly or propagate the full covariance jointly.

### 5. Why omit a long-horizon estimate in a short regime?

**Answer.** The remaining sample may lack residual degrees of freedom.

## Worked reasoning

Before interpreting an estimate, name the outcome unit, shock unit, identifying restrictions, sample and uncertainty method. If any is missing, the numerical sign alone does not support a causal claim. Separate a mechanical accounting identity from a maintained economic restriction. Explain how the answer would change under a different permissible identification without searching until a preferred answer appears. A correct exam response states what can and cannot be inferred, rather than merely naming a test or estimator.

## Reference and further reading

Verified primary reference: https://doi.org/10.1257/0002828053828518

These notes are original explanations written for this portfolio; no thesis text or code was used.
