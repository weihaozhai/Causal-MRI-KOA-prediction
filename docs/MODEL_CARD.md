# Frozen prognostic model

## Inputs

| JSON field | Definition | Encoding |
|---|---|---|
| age | Age at baseline | Years; app accepts 20–100, flags outside 45–79 |
| sex_num | Sex encoding used in development | Male 0, female 1 |
| cart_area_PL | Lateral patellar cartilage abnormality area | MOAKS 0–3 |
| cart_area_FMA | Anterior medial femoral cartilage abnormality area | MOAKS 0–3 |
| bml_size_SS | Tibial-spine BML size | MOAKS 0–3 |

Cartilage-area grades: 0 none; 1 <10%; 2 10–75%; 3 >75%. These are area scores, not full-thickness loss scores. BML-size guidance displayed in the original software: 0 none; 1 <33%; 2 33–66%; 3 >66% of region volume. Confirm compatibility with the scoring protocol used for the manuscript, including any project-specific alternative cutpoints, before scoring new scans. The frozen model and UI scoring definitions were not changed during repository preparation.

## Parameters and equation

`model.json` is the authoritative machine-readable parameter file. The model has 3937 development knee records and 501 replacement events and was fitted using a penalized Cox model (penalizer 0.01). All numerical parameters are preserved from the supplied application.

```text
LP = sum(beta_j * x_j)
centered_LP = sum(beta_j * (x_j - training_mean_j))
p(t | x) = 1 - S_mean(t) ** exp(centered_LP)
```

The lifelines-exported survival is centered at training means. Using uncentered LP with these baseline values would give incorrect probabilities. Baseline survival is 0.9582727790091129 at 5 years and 0.9215466433061293 at 10 years. Group thresholds operate on uncentered LP: median 1.0396564898361427; tertiles 0.695417932634929 and 1.4587587907181327. Higher LP means higher estimated risk.

## Interpretation

The output is a prognostic estimate, not an ATE/CATE or an intervention effect. Death is treated as censoring; probabilities estimate net risk rather than competing-risk cumulative incidence. Cohort-relative risk groups are not treatment thresholds. External absolute-risk calibration, prediction intervals, and clinical utility are not established. Use only for research demonstration and implementation review.

## Reproducibility scope

Public software tests check numerical examples and application behavior with synthetic data. Refitting and verifying the original model requires an independently authorized, identically prepared development dataset. Neither full data preparation nor the causal discovery pipeline is included, so this repository alone cannot reproduce model selection, all external results, or all manuscript figures/tables.
