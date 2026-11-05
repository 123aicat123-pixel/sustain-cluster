# Pre-result addendum: split facility forecast accuracy by workload phase

Status: **2026-11-05, before inspecting the March 9 or September 21 holdout outcomes**. This is a diagnostic addendum to `facility_lag_calibration_protocol_2026-11-05.md`, not a change of training data, ridge lambda, model architecture, or routing algorithm.

## Why this is necessary

The original full simulator period consists of 16 admitted-workload steps followed by 112 drain steps. One-step-ahead predictions have 15 **admission** target timestamps (steps 1..15) and 112 **drain** target timestamps (steps 16..127). Whole-horizon MAE is therefore dominated by drain. An apparently low all-steps MAE can conceal poor predictions exactly when new routing decisions are being made.

On previously explored, retrospectively inspected June 15 and Nov 12 data, persistence (energy of t-1 for t) had admission/drain MAE of 1.271718/0.158182 and 1.543643/0.243388 kWh respectively, pooled over 2 seeds × five DCs, without treating cells as independent trials. This check motivated the **evaluation disclosure**, not any model tuning.

## Locked supplementary evaluation

1. Load the **existing frozen model coefficients** output by the five-day original benchmark. **Never retrain or change lambda/features**. Hash the actual input CSV bytes for each date as additional reproducibility metadata; original split membership hashes remain valid.
2. Reconstruct only adjacent lagged observations within each (date, seed, DC) run.
3. For each date and seed and DC, measure MAE, signed bias, RMSE and absolute-error p95 separately for `1 <= step_index < 16` (admission) and `16 <= step_index < 128` (drain).
4. Compare unchanged `ridge`, `persist`, and training-only `site_mean` methods for **energy kWh and realized facility carbon kg**. Aggregate across DCs using observed cell counts **for description only**; report every date and both seeds.
5. Cross-check the recomputed **all-step** MAE/bias/RMSE against the original benchmark JSON for each date, seed, DC and method. Failure aborts the audit.
6. No model or threshold selection may depend on March 9 / September 21 labels. These calendar days are separate exploratory test cohorts; 5 datacenters × 127 steps and two seeds are NOT independent workload dates.
7. Neither a strong next-step facility forecast nor a strong admission-only forecast validates action-conditioned marginal carbon; online policy comparisons require a separate subsequent protocol and holdouts.

No previous March 9/September 21 labels or model outcomes have been consulted to compose this addendum.
