# Queue-aware online NSGA-II research prototype

**Status:** unverified experiment until the queue-ablation GitHub Actions
run completes successfully. Do not describe these files as published novelty,
a validated scheduling breakthrough, or a proven Pareto improvement.

## Hypothesis

The existing online NSGA-II comparator predicts deadline tardiness from
transfer latency plus a one-batch aggregate-capacity proxy. This ignores
already-running tasks, the backlog in each datacenter and near-future release
of occupied CPU/GPU/memory resources. The new prototype estimates starting
time by simulating a **currently observable** local FIFO queue and current
running-task completion timestamps on the same 15-minute time grid.

Candidate objectives remain proxies (three minimization objectives):
estimated incremental electricity cost, carbon emissions, and positive SLA
tardiness. The additional network externality proxy uses the simulator's
currently visible transmission price matrix, bandwidth and origin carbon
intensity. This is not a calibrated whole-facility model.

## Controlled variants

- `queue_nsga2`: queue projection + incremental network cost/carbon.
- `queue_nsga2_no_queue`: remove queue projection only.
- `queue_nsga2_no_transfer`: remove network cost/carbon from **optimizer
  fitness** only. Physical transfer delay and network accounting in the
  simulator are unchanged.
- `nsga2_surrogate`: previously implemented simpler NSGA-II baseline.
- `sla_feasible_carbon`: previously validated low-computation heuristic.

The three queue-aware variants use the same population (16), generations
(8), local seeded RNG, total-resource candidate set, and choice of final
normalized Pareto compromise (0.1, 0.1, 0.8).


## Verified pilot: negative queue-model ablation

GitHub Actions run:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41790992393

At seed 42, 16 admission steps + 48 drain steps, all five policies
completed the same 417/417 tasks. All runs had zero SLA deadline
violations and passed independent task-level cohort checks.

| Policy | Total cost USD | Total carbon kg | SLA misses |
|---|---:|---:|---:|
| SLA-Carbon | 8393.566 | 29574.180 | 0 |
| NSGA-II surrogate | 8398.326 | 29583.320 | 0 |
| Queue-aware full | 8403.618 | 29624.261 | 0 |
| No queue predictor | 8403.618 | 29624.261 | 0 |
| No transfer externality proxy | 8398.326 | 29583.320 | 0 |

On this uncongested pilot the complete queue predictor produced
**no observed effect**: No-Queue matched the full method on final
cost, carbon, SLA, and task destination changes relative to SLA-Carbon.
The additional network proxy shifted routes and was worse than the
simple method on both cost and carbon. This is evidence *against*
claiming queue/transfer modeling is beneficial under this condition.

Follow-up: an independently recorded 2%/5% CPU-capacity sensitivity
experiment tests whether contention changes this conclusion.
It must not be called favorable without full drain and paired-cohort
verification, and scale-dependent facility energy assumptions require
separate calibration.

## Current limitations and possible confounders

1. Queue predictions omit future arrivals and any uncertainty, and predict
   next-step release on a coarse time grid.
2. The per-core energy proxy (6 W/core) is not the whole SustainDC physical
   energy model (IT, cooling, batteries, standby consumption).
3. The original `nsga2_surrogate` and SLA heuristic use the **current**
   `can_schedule` feasibility check; the queue-aware variants permit
   routing to a presently busy datacenter if its *total* resource capacity
   can eventually fit the task. Thus their comparison is not yet a
   strict algorithm-only ablation; isolate the action-set effect.
4. Network cost is assessed at task launch in the simulator, while the
   proxy uses the price matrix at dispatch. Negative grid electricity
   prices may be physically possible and must not be clipped by a
   benchmarking script.
5. Queue predictions could be optimistic where extra traffic arrives after
   a routing decision; no train/test independent workload dates have yet
   been established.
6. The fixed CPU count stress tests and short 16-step pilot are deliberately
   not publication evidence. Require fully drained task cohorts, no fallback
   or explain fallback fractions, and at least three held-out workload
   *scenarios* in addition to random seeds.

## Verification gates

- Unit checks: immediate local start, running-task resource release,
  existing pending FIFO priority, remote arrival readiness, shared-batch
  contention, and total-capacity infeasibility.
- Pilot: seed 42, 16 admission + 48 drain steps; matched tasks for five
  policies including both ablations.
- Retain and report all results, including null/negative results. Reject
  any run with unmatched cohorts, partial drain, duplicated task or invalid
  SLA timestamps.
- If a successful pilot identifies plausible benefit, replicate under
  larger windows with fixed parameters and separate independent workload
  date/load conditions. Record decision time and unique surrogate calls.

## Reproduction

```bash
python -m unittest discover -s research/tests -p 'test_*.py' -v
python -m research.batch_unified_baselines --steps 16 --drain-steps 48 --seeds 42 \
  --policies sla_feasible_carbon nsga2_surrogate queue_nsga2 \
  queue_nsga2_no_queue queue_nsga2_no_transfer \
  --output-prefix research/results/queue_ablation_pilot
```

All task scheduling here is **independent-job placement** rather than DAG
workflow scheduling; dependency semantics have not been implemented.
