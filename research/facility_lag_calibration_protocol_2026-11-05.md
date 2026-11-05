# Frozen one-step-ahead facility electricity/carbon forecast diagnostic
**Pre-result plan, 2026-11-05. This document is committed before executing the new holdout dates.**

## Purpose and scope
SustainCluster currently routes **independent jobs between data centers**; it is not yet a DAG workflow scheduling simulator. Prior work showed that actual facility carbon differs from the optimizer's naive 6 W/core × duration × instantaneous-CI proxy. This experiment is **offline read-only forecasting**, not a routing algorithm or evidence of marginal carbon causality.

## Fixed splits, no contamination
- Training workload dates: **June 15** and **November 12**, 2023 simulator-local mapped to corresponding 2020 Alibaba trace dates. Already explored.
- Development/validation date: **May 19**, already explored. Report its result but do not choose regression regularization, inputs, or stopping criteria using it.
- Newly selected calendar test dates: **March 9** and **September 21**. These dates are selected for this test here *before consulting their outcomes*; new-date claim is limited to the documented research tests in this branch (other unseen uses cannot be ruled out). After this first result, these dates are no longer untouched.
- Same baseline routing policy in every run: `queue_nsga2_with_transit` (no new decision logic). Seeds **901 and 1701** share each day's trace cohort and are not independent calendar samples.
- CPU capacity 5% in all scenarios. 16 × 15-min fresh admissions plus 112 drain steps, 128 total facility steps; 5 DCs expected. All dispatched tasks must finish, no fallback, facility energy/carbon identities reconciled.
- Training/validation/test **do not mix rows across calendar-date partitions**. Lagged features must never cross simulation runs or data-center boundaries.

## Model and baseline frozen before results
- Task: predict **next simulator-step DC battery-adjusted grid-energy kWh** and carbon kg at time t using **only telemetry from step t−1** plus the deterministic t step index. The model never sees t's IT power, HVAC power, task completions, ambient temperature, CI, or realized carbon at prediction time.
- Per-DC ridge linear regression on lagged `energy_kwh`, IT power kW, HVAC kW, CPU load, running/pending task counts, ambient temperature, effective CI and source CI; known time-of-day sin/cos. Normalize using **training subset only**, fixed ridge penalty **lambda=25**, clip predicted energy at 0. No autoregressive lookahead; no features from later time steps. A per-DC model avoids mixing sites with different facility sizes.
- Convert predicted energy to carbon via last observed effective CI (t−1); this is a practical **lagged-CI baseline, not accurate marginal carbon**. No oracle future CI.
- Comparators: naive **last-step energy persistence** and **last-step carbon persistence** (both use t−1 only), plus per-DC **training-only mean** energy/carbon.
- Metrics: per-date and per-seed MAE, signed bias, RMSE for energy (kWh) and carbon (kg), with corresponding baseline metrics, and per-data-center summary. Report all dates, even worse results. Do not pool time-step rows to claim independent replicates, and do not make significance claims based on 5 DC × 127 step cells.
- Model coefficients and split hashes should be archived; no tuning on held-out dates.

## Explicit limitations and future gate
A lagged forecast of whole-facility energy/carbon is not a decision-specific marginal carbon counterfactual. Any strong results are necessary but **not sufficient** for incorporating it into NSGA-II. For online routing, a later study needs a prospective action-conditional estimator with cooling/storage dynamics and new untouched evaluation dates, while preserving SLA baselines and fair search requests. Facility telemetry collected *after* each step may be used for next-step prediction only, never retroactively injected into that step's dispatch.
