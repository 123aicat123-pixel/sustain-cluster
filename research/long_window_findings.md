# Long-window paired-cohort findings — 2026-11-04

## Provenance and protocol

- CI workflow: `Research longer-window paired-cohort validation`
- Verified run: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41785459528
- GitHub artifact: see `long-window-raw-cohort-evidence` on that run.
- Branch: `research-baselines`; do **not** merge to `main` before a scientific review.
- Workload: bundled Alibaba trace, source admission: 64 x 15 min = 16 hours.
- Drain: 128 x 15 min = 32 hours after stopping new admissions.
- Seeds: 1, 42, 2026; common policy-specific resets.
- Four policies: `lowest_carbon`, `lowest_price`, `round_robin`, `sla_feasible_carbon`.
- All policies pass the **same task-level environment action path**, with local
  immediate placement and remote network transfer delay. This is an adapted
  comparison, not the upstream RBC implementation verbatim.
- All 12 runs completed **1,816/1,816** dispatched tasks, with zero unfinished,
  queued, or in-transit at the horizon, no policy-selector fallbacks, and
  independent recomputation of each task's SLA flag.
- The task-level cohort parser asserted matching seed/task name, arrival,
  duration, deadline and origin, and created paired rescue/harm counts.
- Simulator cost and carbon calculations were cross-checked per data-center
  step against its own reported energy, electricity price and carbon intensity.
  This is a mathematical consistency check, **not physical-world validation**.

## Seed-level outcomes

| Seed | Lowest Carbon: cost USD | Lowest Carbon: carbon kg | Lowest Carbon: SLA misses | SLA-Carbon: cost USD | SLA-Carbon: carbon kg | SLA-Carbon: SLA misses |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 26590.704 | 79524.670 | 332 | 26392.041 | 79610.925 | 41 |
| 42 | 26136.313 | 90964.802 | 343 | 26270.178 | 91484.937 | 55 |
| 2026 | 24365.048 | 85361.182 | 330 | 24336.944 | 85551.534 | 2 |

Across these three specific seeds: Lowest Carbon 1,005/5,448 SLA misses
(18.45%); SLA-Carbon 98/5,448 (1.80%); relative miss-count reduction 90.25%.
This aggregate is **not** 5,448 statistically independent replications.

Paired task comparisons (SLA-Carbon versus Lowest Carbon):

| Seed | SLA rescued | SLA harmed | Net fewer misses |
|---|---:|---:|---:|
| 1 | 301 | 10 | 291 |
| 42 | 313 | 25 | 288 |
| 2026 | 328 | 0 | 328 |

On the same seeds, reported mean total cost is USD 25,697.36 for Lowest
Carbon and USD 25,666.39 for SLA-Carbon. Carbon is slightly **higher** for
SLA-Carbon in every one of these three long-window scenarios: this is an
SLA-versus-carbon tradeoff, not proof of Pareto dominance.

## What remains unproven

1. Multiple independent dates / workload regime splits and >3 independent
   scenario replications (three seeds alone do not support significance).
2. SLA scheduling under real queueing/contention; current policy uses a
   no-contention earliest-finish estimate and a common fallback on infeasibility.
3. Model calibration: energy price units, grid carbon intensity, PUE/battery
   effects, data transfer model and economically meaningful negative tariffs.
4. A fair, trained SAC comparator and independently verified multiobjective
   optimizer using the *same* action permissions and comparable budgets.
5. Sensitivity to the local-transfer fastpath, horizon, drain cutoff,
   CPU capacity and workload size.

Earlier native RBC and v1 routing results must never be pooled with this v2
shared-action-path dataset. The initial attempt to audit all energy/price
values as nonnegative failed in CI; signed electricity prices were subsequently
accepted while preserving mathematical consistency checks. Both failed and
successful CI runs are retained as an audit trail.

**Publication status: exploratory, reproducible within these settings; not a
confirmed general algorithm-performance claim.**
