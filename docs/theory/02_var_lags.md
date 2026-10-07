# VAR estimation and lag choice

Status: draft for review

## Question and intuition

A VAR lets each variable depend on its own and other variables' past values. This captures predictive feedback, not necessarily causal effects. The intercept, month dummies and predeclared transition dummies are part of the model; dropping them changes the estimand.

## Model and assumptions

$y_t=c+D_td+\sum_{j=1}^p A_j y_{t-j}+u_t$. Conditional OLS estimates each equation. $\widehat\Sigma=U^\prime U/T$ is positive semidefinite even when equations have different masks. Information criteria compare fit with a penalty for parameter count; a common sample is required across candidate lags.

## Interpretation and common errors

Adding lags reduces truncation error but increases variance and consumes degrees of freedom. BIC penalizes complexity more strongly than AIC in ordinary samples. A residual-LM rule complements information criteria: an economical lag may still leave predictable residuals. The selected lag is a data-dependent choice, so conventional bands conditional on it do not propagate lag uncertainty. Roots of the companion matrix summarize fitted stability; inverse-root conventions must not be confused.

## Portfolio application

The project starts at the BIC lag and checks successive lags through the approved maximum. The passing criterion is explicitly described in DECISIONS.md; the complete search is saved. If none passes, the fallback is flagged rather than called white noise. TR external equations exclude domestic lags. This is a substantive small-open-economy restriction, not a computational shortcut. Check remaining dependence at higher diagnostic orders before interpreting iid residual resampling.

```{=typst}
#pagebreak()
```

## Exam practice

### 1. What does an off-diagonal VAR coefficient mean?

**Answer.** A conditional predictive association at that lag, not a structural causal effect.

### 2. Why compare IC on a common sample?

**Answer.** Otherwise differing observations confound the fit comparison.

### 3. Why can BIC be insufficient?

**Answer.** A low-dimensional fit may retain serially correlated innovations.

### 4. What is block exogeneity?

**Answer.** The designated external block does not dynamically respond to domestic variables in the model.

### 5. What does a companion root above one imply?

**Answer.** The fitted recursion is unstable; finite-horizon calculations still exist but long-run stationary inference is fragile.

## Worked reasoning

Before interpreting an estimate, name the outcome unit, shock unit, identifying restrictions, sample and uncertainty method. If any is missing, the numerical sign alone does not support a causal claim. Separate a mechanical accounting identity from a maintained economic restriction. Explain how the answer would change under a different permissible identification without searching until a preferred answer appears. A correct exam response states what can and cannot be inferred, rather than merely naming a test or estimator.

## Reference and further reading

Verified primary reference: https://doi.org/10.2307/2938337

These notes are original explanations written for this portfolio; no thesis text or code was used.
