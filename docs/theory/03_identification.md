# Identification and Cholesky

Status: draft for review

## Question and intuition

Reduced-form residuals mix structural shocks. Identification asks which economic disturbance generated them. A covariance matrix alone generally cannot distinguish monetary policy, demand, supply and information shocks. Timing assumptions add restrictions that must be defended.

## Model and assumptions

$u_t=B\varepsilon_t$, $E[\varepsilon_t\varepsilon_t^\prime]=I$, hence $\Sigma=BB^\prime$. A lower-triangular Cholesky factor chooses one of many admissible decompositions. Ordering a variable before policy means its impact response to that policy shock is zero.

## Interpretation and common errors

Normalize the shock explicitly: a one-unit structural innovation is not a 100 bp tightening unless the policy impact has been rescaled. With monthly averages, the central bank may react inside the same month to exchange-rate movements. A policy-before-FX ordering can therefore recover a contemporaneous response to depreciation rather than an exogenous tightening. Swapping the ordering changes identifying restrictions; it is not a harmless relabelling.

## Portfolio application

EA two-year yields reflect expectations and information as well as policy actions. High-frequency surprises add an external instrument if relevant and exogenous to non-policy structural shocks. A strong first-stage F addresses relevance only. Information contamination, event-window choice and sample alignment remain substantive issues. Sign restrictions identify a set, and medians across rotations need not correspond to one admissible model.

```{=typst}
#pagebreak()
```

## Exam practice

### 1. Does Cholesky prove exogeneity?

**Answer.** No. It imposes recursive timing restrictions.

### 2. What changes when FX precedes policy?

**Answer.** Policy cannot move FX on impact; policy may react to FX contemporaneously.

### 3. Why normalize a tightening?

**Answer.** To compare responses to a common policy-indicator impact rather than shock variance.

### 4. What does a strong first stage establish?

**Answer.** Instrument relevance under the reported test, not exclusion.

### 5. Why label sign spread differently from a CI?

**Answer.** Rotation variation is identification uncertainty conditional on the reduced form, not sampling coverage.

## Worked reasoning

Before interpreting an estimate, name the outcome unit, shock unit, identifying restrictions, sample and uncertainty method. If any is missing, the numerical sign alone does not support a causal claim. Separate a mechanical accounting identity from a maintained economic restriction. Explain how the answer would change under a different permissible identification without searching until a preferred answer appears. A correct exam response states what can and cannot be inferred, rather than merely naming a test or estimator.

## Reference and further reading

Verified primary reference: https://doi.org/10.1016/j.jmoneco.2019.08.016

These notes are original explanations written for this portfolio; no thesis text or code was used.
