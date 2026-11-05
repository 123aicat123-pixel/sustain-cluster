# All-datacenter dispatch feasibility: audited research milestone

Date: **2026-11-05**. Evidence: [GitHub Actions run 41969497344](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41969497344),
`action-feasibility-observation` **SUCCESS** at code commit `483f51a4`.
The action artifact **sci-carbon-action-feasibility** (ID `13389092240`)
contains the aggregate JSON and per-task JSONL candidate tables.
The `policy-contracts` job also passed **96 tests** on that commit.

## Evaluation design

- Same queue-aware `fixed_30` routing and common manual simulator action path.
- Synthetic scaled datacenter CPU/GPU/memory: 2% and 10%.
- Later chronological test windows beginning at ticks 288 and 448.
- Paired random seeds: 1, 42; identical actual arrivals across capacities.
- 5 candidate DCs; every job evaluated on all centers using current running
  and FIFO pending work, already in-transit jobs and earlier batch
  commitments. The target job is evaluated **before** being committed.
- No actual completion, hidden future arrivals or future grid carbon
  may enter any candidate forecast. Deadline labels are joined after
  simulation; unfinished tasks are censored.
- A predicted feasible alternative is *not* a proven causal SLA rescue.
  A different route would alter future queues and job outcomes.
  Observed carbon grid intensity is not measured marginal CO2.

## Per-seed results

`No feasible` means all candidate predicted completion times exceed the
deadline or have no bounded forecast. `No buffered` requires finish +30
minutes <= deadline. Values count **tasks**, not center candidates.

| Capacity | Window | Seed | Admitted | Finished | No predicted feasible DC | No buffered-feasible DC | Actual deadline failures (incl. overdue) |
|---|---|---|---:|---:|---:|---:|---:|
| 2% | 0 | 1 | 313 | 310 | 189 | 218 | 197 |
| 2% | 0 | 42 | 313 | 310 | 186 | 215 | 201 |
| 2% | 1 | 1 | 448 | 439 | 277 | 336 | 292 |
| 2% | 1 | 42 | 448 | 440 | 261 | 333 | 277 |
| 10% | 0 | 1 | 313 | 313 | 68 | 121 | 68 |
| 10% | 0 | 42 | 313 | 313 | 68 | 121 | 72 |
| 10% | 1 | 1 | 448 | 448 | 133 | 241 | 140 |
| 10% | 1 | 42 | 448 | 448 | 132 | 241 | 145 |

Across the **four runs per capacity** (1522 job admissions, including the
same workload in both seeds, so NOT 1522 independent observations):

| Measure | 2% synthetic capacity | 10% synthetic capacity |
|---|---:|---:|
| Admitted | 1522 | 1522 |
| No predicted feasible DC (unbuffered) | 913 / 1522 (**60.0%**) | 401 / 1522 (**26.3%**) |
| No predicted 30-min-buffered feasible DC | 1102 / 1522 (**72.4%**) | 724 / 1522 (**47.6%**) |
| None forecastable within bounded horizon | 20 / 1522 (1.3%) | 0 |
| Actual SLA failure incl overdue | 967 / 1522 (**63.5%**) | 425 / 1522 (**27.9%**) |
| Selected forecasted late despite another forecasted feasible DC | **0** | **0** |
| Among jobs with buffered-feasible centers, chosen center minimizes observed grid intensity | **100%** | **100%** |

## Interpretation and methodological caution

**The zero missed alternatives and 100% selection consistency are
expected from the implemented baseline policy.** Its dispatch rule
already chooses the lowest instantaneous carbon-intensity center
among available buffered-feasible queue forecasts; otherwise it
minimizes optimistic predicted completion time. This agreement
provides a useful implementation consistency check, NOT evidence
of novel or superior scheduling performance.

The dominant bottleneck under severe resource pressure is the size
of the **predicted feasible action set**: for many jobs the bounded,
future-arrival-blind FIFO model predicts no on-time center. Increasing
risk buffers makes the predicted feasible set *smaller*, which cannot
by itself make these jobs meet the deadline. At 10% capacity, actual
deadline misses exceed the no-unbuffered-feasible count by 24 across
the four runs, consistent with a remaining role for forecast errors.
But aggregate subtraction alone does NOT identify causal avoidable
misses, and the same task arrivals reoccur across seeds.

A no-forecast result is **epistemic uncertainty within a finite
prediction horizon**, NOT proof of physical impossibility. A late
prediction is likewise not a formal impossibility certificate; later
arrivals and controls may change the system. The study does NOT
establish formal SLA probability coverage, conditional risk
calibration, or incremental routing carbon benefits.

This setting still models **independent jobs, not DAG workflows**.

## Next research decisions

1. Treat **feasible action-set scarcity** separately from
   conditional forecast uncertainty. Measure no-slack and
   no-forecast tasks before imposing risk margins.
2. On earlier validation windows only, test practical alternatives
   that can increase deadline feasibility: bounded admission/deferral
   of queued work, task-priority/urgency ordering, or state-dependent
   reservation; distinguish these from infeasible hard deadlines.
3. For methods changing routing or priorities, rerun the full
   matched simulator rather than calling one-job hypothetical
   alternatives real SLA rescues.
4. Predeclare carbon/SLA/throughput tradeoffs; compare exact
   completed job sets and count censored overdue work.
5. Expand to independent chronological workload windows and
   realistic full-capacity regimes before pursuing an SCI claim.
