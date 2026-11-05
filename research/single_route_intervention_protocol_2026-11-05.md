# Controlled single-route interventions for action-conditioned facility carbon (exploratory)

**Pre-result registration, 2026-11-05**. Scope: SustainCluster independent task placement (NOT DAG scheduling). This is a fixed-simulator *intervention* feasibility and carbon accounting check, not deployment validation. Do not describe correlated seeds or task-step samples as independent dates.

## Why a different experiment

Earlier whole-facility t-1 ridge predictor on June 15/Nov 12 training dates failed the March 9/Sept 21 held-out tests relative to simple t-1 persistence. Whole-facility forecast accuracy is insufficient for **marginal carbon caused by a route choice**.

## Frozen first intervention

For each workload/scenario and seed, run the **same deterministic `round_robin` policy** three times, in the same simulator per-task action path, with only one action (the first eligible dispatch batch) allowed to differ:

- `control`: no route mutation; determine and log the same eligible task.
- `low_ci`: route that same eligible task to the *lowest currently observed effective grid CI* alternative DC, excluding the control action; stable dc_id tie break.
- `high_ci`: route the task to the *highest currently observed effective grid CI* alternative DC, excluding the control action; stable dc_id tie break.

The **single task** is the eligible first-batch job with largest known `cores_req × duration`, stable index tie break; alternative feasibility requires task CPU/GPU/memory request <= each alternative's **total** capacity. Current CI is observable before dispatch, but results must not use future carbon, future workload or finished-task labels to choose. No other routing actions may be modified. The deterministic round-robin policy and seed initialization are identical across arms. Distinct arm names identify all telemetry and completion rows.

## Fixed exploratory settings

Already explored June 15 and Nov 12, simulated calendar 2023 / 2020 Alibaba workload mapping, 5% CPU capacity, seeds **901 and 1701**, 16 × 15min admission + 112 drain steps, 5 data centers. 2 dates × 2 seeds × 3 arms = **12 complete simulator runs**; do not suppress unfavorable or null outcomes. These dates are development evidence, not new untouched tests.

Require: all tasks finished and same identities, all but one initial dispatch action identical, zero fallback and identical admissions, complete 128×5 facility cells and validated facility energy/cost/CO2 accounting. Report arm-level realized SLA misses, facility and transmission carbon separately, costs, IT and HVAC power attribution. Differences include induced downstream resource contention and any later changed start times: they are a simulated **total intervention effect**, not isolated per-task marginal watts or a causal deployment claim.

**Research gate:** if the intervention shows reproducible action sensitivity not captured by fixed 6W/core proxy, build a training-only, action-conditioned model from independent intervention runs; *do not* tune it or claim success using these explored days alone. Preserve the current With-Transit best SLA baseline untouched. Neither low-grid-CI route nor high-grid-CI route is expected always to be better.
