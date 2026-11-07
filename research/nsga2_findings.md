# NSGA-II online proxy baseline — validated integration (2026-11-04)

## Algorithm and evaluation design

- Source: `research/nsga2_core.py`, `research/nsga2_batch_policy.py`.
- Fully independent three-objective NSGA-II core: non-dominated sorting,
  crowding distance, binary crowded tournament, one-point crossover,
  per-gene mutation, elitist combined-parent/offspring selection.
- Online per-batch chromosome: one numerical data-center ID per currently
  observed task. No future workload information is used.
- Optimizer objectives are **surrogates**, not actual simulator cost/carbon
  or SLA outcomes: (estimated incremental electricity cost, carbon, positive
  deadline tardiness). Proxy electricity consumption is 6 W/core plus an
  approximate within-batch load penalty, and does NOT include full plant
  / battery / PUE / network consumption physics.
- Compromise selection: normalized non-dominated-front weighted score using
  immutable weights (cost 0.1, carbon 0.1, tardiness 0.8).
- Population size: 16; generations: 8; mutation rate: 1 / tasks in batch;
  seeded, reproducible RNG.
- Record **both** fitness evaluation requests (including cached ones) and
  unique actual surrogate evaluations. These are not wall-clock measurements.
- Important: online NSGA-II has more planning computation than heuristic
  baselines. A fair final paper must report decision runtime and matched
  computational budgets when comparing optimizers, not just total outcomes.

## Verified seed-42 short pilot

CI: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41788095305

- 32 admissions steps (8 hours) + 64 drain steps.
- 776/776 tasks completed for each of three policies, with matched task cohort.
- Cost USD: Lowest Carbon 13156.696; SLA-Carbon 13128.190;
  NSGA-II 13132.483.
- Carbon kg: Lowest Carbon 46973.264; SLA-Carbon 46975.318;
  NSGA-II 46983.012.
- SLA misses: Lowest Carbon 127; SLA-Carbon 0; NSGA-II 6.
- NSGA-II: 32 batch optimizations, 12,800 surrogate fitness requests,
  3,411 unique surrogate evaluations.
- **Negative result**: NSGA-II did not beat the simpler SLA-aware heuristic
  in cost, carbon, or SLA for this pilot run.

## Additional fixed-parameter validation

CI: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41788506920

- 64 admission steps (16 hours) + 128 drain steps (32 hours).
- Same batch optimization parameters; **no tuning on pilot seed 42**.
- Seeds 1, 2026, 31415. Note seeds 1 and 2026 appeared in earlier
  *heuristic* exploratory testing, so this is a seed-42-excluded NSGA-II
  validation, not a pristine unpublished blind test.
- 9/9 policy-run pairs finished with 1,816/1,816 jobs each, matched cohorts,
  no optimizer fallback, all tasks finished within the fixed drain.
- Mean results across these 3 seeds:

| Policy | Cost USD (mean) | Carbon kg (mean) | SLA misses (total / 5,448) |
|---|---:|---:|---:|
| Lowest Carbon | 25643.786 | 81390.135 | 1006 |
| SLA-Carbon | 25578.646 | 81529.372 | 102 |
| NSGA-II surrogate | 25513.264 | 81580.467 | 113 |

- SLA misses per seed (1 / 2026 / 31415):
  Lowest Carbon 332 / 330 / 344;
  SLA-Carbon 41 / 2 / 59;
  NSGA-II 41 / 6 / 66.
- Thus lowest mean electricity/transfer cost is NSGA-II, lowest average
  carbon is Lowest Carbon, and lowest SLA misses is SLA-Carbon. None of
  these is globally superior on all three final simulator metrics.
- Three seeds are too few for a significance claim; task observations
  within each seed are correlated. Avoid treating all 5,448 tasks as
  independent experimental replications.
- Simulated physical accounting identities, SLA task timeline and lifecycle
  conservation were checked. Physical calibration remains open.


## Fresh-seed extension (no parameter change)

GitHub Actions:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41788998616

Three additional seeds (27182, 12345, 8080) ran with 64 admission
steps and 128 drain steps, 1,816 tasks per run, zero unfinished jobs,
zero fallback, and validated paired cohorts.

| Policy | Mean USD total cost | Mean kg carbon | SLA misses / 5,448 |
|---|---:|---:|---:|
| Lowest Carbon | 24594.097 | 80256.706 | 1016 |
| SLA-Carbon | 24539.036 | 80438.294 | 76 |
| NSGA-II surrogate | 24413.146 | 80438.769 | 83 |

Paired violations by seed (27182 / 12345 / 8080):
Lowest Carbon 340 / 330 / 346;
SLA-Carbon 24 / 29 / 23;
NSGA-II 41 / 18 / 24.

NSGA-II cost is lower than SLA-Carbon in all three additional seeds;
its mean reduction is USD 125.89, or approximately 0.51% of
SLA-Carbon's mean cost. On this extension, NSGA-II has 7 more
SLA misses across three seeds and nearly equal mean carbon (+0.475 kg).
This is a descriptive tradeoff, NOT a statistically established advantage.
A fixed compromise weight chosen without domain calibration can shift the
observed tradeoff; this is a case for *pre-registered* ablations, not
test-set tuning. All outcomes depend on the current simulator assumptions.

## Research implications and next validation gates

1. Learn whether prediction errors are dominated by transfer delay, queue
   interference, or energy-proxy mismatch; use independent held-out workloads.
2. Replace the heuristic cost/carbon proxy with calibrated, strictly
   past-observable estimates. Keep the held-out test split untouched.
3. Compare NSGA-II to simpler spatial routing, a correctly trained SAC,
   and ablation versions of each forecasting/robustness component.
4. Report Hypervolume / IGD for genuinely multi-solution Pareto methods,
   and also decision time, outcome variance and SLA constraint violation.
   A single chosen route per timestep is not itself a Pareto set of
   whole-episode outcomes.
5. Sweep independent arrival dates, load intensity, transfer latency,
   electricity rates and carbon intensity under controlled ablations.

**Status:** integration and fixed-parameter smoke comparisons validated;
NOT publication-grade algorithm superiority or proof of originality.
