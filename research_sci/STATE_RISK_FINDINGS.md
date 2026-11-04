# Decision-time pressure and forecast error diagnosis

**Date:** 2026-11-04  
**Verified evidence:** [GitHub Actions run 41823647128](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41823647128), `state-risk-observation` SUCCESS; `policy-contracts` SUCCESS.
Comparison reference (before adding runtime lower bound): [run 41822914723](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41822914723), `state-risk-observation` SUCCESS. Synthetic capacity 2% and 10%, fixed 30-minute queue policy, seeds 1/42, two later windows, one seven-day common simulator horizon. This audit **does not modify scheduling decisions**.

## Operational evidence — prediction error and SLA do not coincide

| Capacity | Future window | Seed | Admitted | Finished | Forecast MAE (minutes) | Mean optimistic error (minutes) | Deadline misses incl. overdue |
|---|---|---:|---:|---:|---:|---:|---:|
| 2% | 0 | 1 | 313 | 310 | 36.00 | +29.42 | 197 |
| 2% | 0 | 42 | 313 | 310 | 45.53 | +30.44 | 201 |
| 2% | 1 | 1 | 448 | 439 | 62.80 | +57.13 | 292 |
| 2% | 1 | 42 | 448 | 440 | 68.01 | +61.94 | 277 |
| 10% | 0 | 1 | 313 | 313 | 0.91 | +0.53 | 68 |
| 10% | 0 | 42 | 313 | 313 | 2.49 | +2.01 | 72 |
| 10% | 1 | 1 | 448 | 448 | 1.91 | +1.77 | 140 |
| 10% | 1 | 42 | 448 | 448 | 4.29 | +3.95 | 145 |

- On four 2%-capacity episodes, prediction errors are substantial and
  generally early/optimistic. 23 jobs remain censored across the four
  episodes, and are not assigned fictitious zero error.
- On four 10%-capacity episodes, nearly all completed-task forecasts
  match within a few minutes, yet many deadlines are still missed.
- **No test job had a negative immediate-execution slack** at dispatch:
  `deadline - dispatch_time - task.duration < 0` was **zero cases**
  in all eight episodes. This is only a necessary lower bound that ignores
  network transfer, resource contention and 15-minute dispatch ticks.
  The deadline misses are therefore not explained by execution duration
  alone being too long *at dispatch*.
- At 10% capacity, the numbers of tasks whose **queue-predicted finish**
  already exceeds deadline are: seed1/window0 **68**, seed42/window0
  **68**, seed1/window1 **133**, seed42/window1 **132**. Among the
  actually completed tasks in these groups, all of these predicted-late
  jobs later missed their deadlines. In the same episodes total actual
  deadline misses were 68,72,140,145. Most late jobs are therefore
  identifiable at dispatch despite low prediction MAE.
- At 2% capacity, the predicted-late counts were 186/183 (window0)
  and 270/254 (window1). Real deadline-failure counts were 197/201 and
  292/277 (including overdue unfinished). Forecast optimistic errors
  can hide further missed deadlines.

## Pressure features

The audit captures strictly **pre-decision** CPU/GPU/memory usage, pending
and running tasks, known incoming and same-batch commitments, pending
core-minutes, observed carbon intensity, risk margin, predicted deadline
slack and intrinsic immediate-execution deadline slack. Task finish-time
and actual SLA labels are joined only **after** completion; unfinished
tasks are explicitly censored. Predeclared pressure bins have per-group
dispatch, completed, censored and forecast-evaluable counts.

In 2% capacity, 3 of 4 episodes have higher forecast MAE among jobs
dispatched to centers with a nonempty pending queue than to centers
with empty pending queues. The fourth episode has a higher empty-queue
MAE because outlier error and task-mix effects differ. This
**does not establish a universally monotone queue-pressure effect**.
CPU utilization is also not monotonically associated with error.
At 10%, MAE remains low across bins.

## Scientific interpretation / next gate

A model that predicts finish time accurately cannot fix a selected
placement that is predicted to miss the deadline already. This
motivates separating:

1. **Dispatch-time feasible/actionable set:** Do any candidate data
   centers have forecast finish <= SLA deadline? Count tasks for which
   none does, rather than declaring that adding a safety buffer fixes them.
2. **Prediction uncertainty:** Conditional forecast-error risk, trained
   and calibrated using earlier windows only, evaluated on independent
   later time cohorts.
3. **Carbon tradeoff under actual task completion:** Compare same
   admitted and completed task sets, with unfinished/overdue jobs counted.

Next build a *read-only all-datacenter feasibility audit* at decision
time (without future knowledge), then assess how often chosen routes
miss a feasible lower-carbon or earlier-completion alternative. Do
not claim an adaptive-risk algorithm benefit, SCI significance, causal
generalization or formal chance-constraint coverage from these
descriptive, small synthetic stress experiments.

This is still **independent task scheduling, not DAG workflow scheduling**.
