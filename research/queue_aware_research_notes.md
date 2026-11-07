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


## Verified capacity-stress result: queue prediction matters under contention

GitHub Actions:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41791930845

Conditions: unchanged incoming Alibaba task cohort, seed 42, 16 steps
admission + 112 steps drain, with only total CPU core count scaled via
temporary datacenter configs. Absolute costs/carbon **cannot** be compared
across scale factors as if they were the same physical plant.

### CPU capacity scale = 5% (all 417 tasks finish)

| Policy | Cost USD | Carbon kg | SLA misses |
|---|---:|---:|---:|
| SLA-Carbon | 1275.087 | 4355.207 | 140 |
| Original NSGA-II surrogate | 1278.668 | 4365.683 | 131 |
| Queue-aware NSGA-II | 1233.314 | 4592.977 | 126 |
| Queue-aware minus queue prediction | 1230.030 | 4260.029 | 167 |
| Queue-aware minus transfer-cost proxy | 1238.403 | 4593.316 | 123 |

All five policies completed 417/417 tasks, no fallback actions, matched
task-level comparisons were evaluated against No-Queue, and the audited
simulator lifecycle/accounting invariants held. The queue model reduced
missed deadlines by **41 tasks (24.6%) relative to its otherwise matched
No-Queue ablation** (167 -> 126), at a +USD 3.284 cost and +332.948 kg
carbon cost *in this one test condition*. It also reduced misses
versus SLA-Carbon (140 -> 126) at lower cost (USD 1275.087 -> 1233.314)
but much higher carbon (4355.207 -> 4592.977 kg).

The complete algorithm did NOT dominate the carbon-aware baselines;
cost/carbon/SLA tradeoffs remain substantial. No hypothesis of a universally
beneficial queue model has been validated.

### CPU capacity scale = 2% (CENSORED — not a valid ranking)

- SLA-Carbon: 388/417 completed, 29 unresolved.
- Original NSGA-II: 417/417 completed, **27.6% fallback assignments**.
- Queue-aware full: 417/417 completed, zero fallback.
- No-Queue: 357/417 completed, 60 unresolved.
- No-Transfer: 417/417 completed, zero fallback.

The partially completed task cohorts are different: a naive comparison of
reported cost, carbon and SLA misses would be **invalid and biased**.
The CI explicitly labels this scenario CENSORED and skips completed-cohort
paired ranking. This constitutes evidence that tighter capacity can stress
system completion and routing feasibility.

### Next scientific gates

1. Repeat the 5% experiment with multiple seeds and **independent trace
   dates**; evaluate the seed-paired miss-count differences and uncertainty.
2. Isolate candidate-action-space differences between original NSGA-II
   and the queue-aware class; all three queue-aware variants already share
   the same candidate set and genetic budget.
3. Validate the queue projector against task-level actual starts and
   investigate why the full model pays higher carbon emissions under
   contention. Record per-decision runtime and forecast error.
4. Avoid mixing 2%-capacity censored data into a paper average; either
   extend to full drain for all algorithms or report coverage/outstanding
   work as a separate outcome.
5. Do not call the algorithm original until a substantive literature novelty
   search and independent comparison are completed.


## Three-seed 5%-capacity verification — benefit not robust

Verified CI: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41794110427

- 3 seeds (27182, 12345, 8080), five policies, 15 full-simulator
  runs; all 417/417 admitted tasks finished for every run, zero fallback,
  independent SLA and exact matched-cohort audits passed.
- Queue full versus **otherwise identical No-Queue** SLA misses:

| Seed | Full | No-Queue | Fewer misses (No-Queue minus Full) | Full carbon kg | No-Queue carbon kg |
|---|---:|---:|---:|---:|---:|
| 27182 | 111 | 157 | +46 | 3818.493 | 3664.114 |
| 12345 | 144 | 135 | -9 | 3835.459 | 3595.361 |
| 8080 | 128 | 125 | -3 | 3848.535 | 3673.382 |

- Aggregate of these three task sets: 383 vs 417 SLA misses, a net
  reduction of 34. But **only one of three seeds benefits**, with worse
  SLA in two, so previous single-seed claims about consistent improvement
  are unsupported. These seeds are not separate workload dates.
- Full method increases actual carbon emissions in **all** three seeds.
  A reduction in SLA deadline violations cannot be described as a
  three-objective Pareto improvement here.

### Independent emission-accounting decomposition (seed 42)

Verified attribution CI:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41794740577

For Full minus No-Queue, total +332.949 kg realized carbon:
+329.983 kg **facility** (99.1% of increase) and +2.965 kg
transmission. Cost change: -USD 14.259 facility, +USD 17.542
transmission, net +USD 3.283. Full policy additionally remotely
routed 30 tasks. The carbon increase is **not mainly attributable to
network transfer emissions**; route-dependent facility energy/carbon
is the more important target for the next model. This decomposition
only checks the simulator's bookkeeping, not real-world causality.

## Carbon-guard policy hypothesis (not a proven correction)

`queue_nsga2_carbon_guard` uses the *same* queue-aware NSGA-II
population, generations, random choices, transfer model and candidate
action set. After the optimizer chooses its chromosome, it compares
its **estimated incremental carbon proxy** against the heuristic
SLA-Carbon seed chromosome, replacing it with that seed if proxy
carbon exceeds the seed's proxy carbon.

This is a strict zero-margin proxy-carbon budget, **not** a guarantee
on actual facility carbon emissions or SLA. It makes two extra
surrogate-fitness function calls per nonempty decision batch (reported
separately), but does not increase NSGA-II genetic search evaluations.
Report intervention counts and physical metrics; a failure to reduce
real carbon is an important falsification of this simple proxy model.

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
