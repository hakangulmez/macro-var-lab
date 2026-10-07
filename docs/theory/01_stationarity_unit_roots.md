# Stationarity and unit roots

Status: draft for review

## Question and intuition

Why does persistence change inference? Weak stationarity requires a constant mean and autocovariances that depend on distance, not calendar time. A unit-root process accumulates innovations; shocks do not dissipate. A deterministic trend differs from a stochastic trend because detrending can remove the former without removing accumulated shocks.

## Model and assumptions

$y_t=\rho y_{t-1}+u_t$. For $|\rho|<1$, $\mathrm{Var}(y_t)=\sigma_u^2/(1-\rho^2)$ in the stationary distribution. For $\rho=1$, $\mathrm{Var}(y_t)=t\sigma_u^2$ conditional on a fixed initial value. An I(1) series becomes stationary after one difference; an I(2) series requires two.

## Interpretation and common errors

ADF and PP test a unit-root null; KPSS tests stationarity. Disagreement is evidence of uncertainty, not a vote to be resolved by whichever test supports a desired result. Zivot-Andrews allows a single estimated break under a specific alternative, but does not identify a policy regime causally. Near-unit roots and short samples make both rejection and non-rejection difficult to interpret. ADF lag and deterministic terms must be reported. Seasonal adjustment and changes in index bases can affect test behaviour.

## Portfolio application

In this project, baseline levels preserve standard monetary-VAR practice. The approved TR rule tests levels first and changes prices to monthly inflation only on its predeclared trigger. Marginally explosive fitted roots do not automatically invalidate finite-horizon impulse calculations. They do weaken stationary-bootstrap coverage claims. The response of inflation and the cumulative response of the price level are different objects.

```{=typst}
#pagebreak()
```

## Exam practice

### 1. What is weak stationarity?

**Answer.** Constant finite mean/variance and covariance depending only on lag.

### 2. How does a random walk differ from a trend-stationary series?

**Answer.** Random-walk shocks have permanent level effects; trend-stationary deviations revert.

### 3. Can an ADF non-rejection prove I(1)?

**Answer.** No. It may reflect low power, breaks or a wrong deterministic specification.

### 4. Why test the first difference?

**Answer.** To assess whether one difference is sufficient and whether I(2) remains plausible.

### 5. Must every monetary VAR be differenced?

**Answer.** No. Levels preserve long-run information; assumptions and inference limits must be explicit.

## Worked reasoning

Before interpreting an estimate, name the outcome unit, shock unit, identifying restrictions, sample and uncertainty method. If any is missing, the numerical sign alone does not support a causal claim. Separate a mechanical accounting identity from a maintained economic restriction. Explain how the answer would change under a different permissible identification without searching until a preferred answer appears. A correct exam response states what can and cannot be inferred, rather than merely naming a test or estimator.

## Reference and further reading

Verified primary reference: https://doi.org/10.2307/2938337

These notes are original explanations written for this portfolio; no thesis text or code was used.
