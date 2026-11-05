# Pareto-front lower-proxy-carbon, aggregate SLA-risk gate: negative results (2026-11-05)

## Evidence and scope

Verified GitHub Actions success after correcting an invalid *path-dependent unique cached evaluations must equal* assertion:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41979857450

All three matrix jobs succeeded with 18 full simulator policy runs: 3 dates/capacities × 2 seeds × Queue-NSGA-II, With-Transit, and the front-carbon-risk postselector. Every run completed all admitted tasks, with zero fallback. Same seeds/cohorts and fixed optimizer request budget. The original failed run was due to an overly strict comparison of the number of distinct evaluated chromosomes, which can vary when decisions change subsequent state. Its partial files are not used as confirmation of CI success.

The lower-carbon candidate is drawn from the NSGA-II *already-evaluated* final Pareto front and must not increase total **predicted** tardiness or count of **predicted** SLA misses relative to the With-Transit knee. It does not use future tasks or observed final-simulator carbon during selection.

## Realized outcomes (front-carbon-risk MINUS With-Transit)

| Workload date | CPU scale | Seed | With-Transit SLA misses | Front-carbon-risk SLA misses | Carbon delta kg | Cost delta USD | Front swaps |
|---|---:|---:|---:|---:|---:|---:|---:|
| June 15 | 5% | 901 | 6 | 16 | -65.353 | -14.593 | 8 |
| June 15 | 5% | 1701 | 24 | 18 | +27.759 | +3.048 | 6 |
| Nov 12 | 5% | 901 | 13 | 26 | -5.399 | +6.290 | 3 |
| Nov 12 | 5% | 1701 | 20 | 21 | -5.542 | +4.379 | 6 |
| May 19 | 10% | 901 | 1 | 1 | -3.764 | -0.473 | 4 |
| May 19 | 10% | 1701 | 2 | 1 | -31.823 | -6.947 | 6 |

The observed carbon decreased in five of six conditions, but four conditions had equal or worse realized SLA, including a deterioration from 13 to 26 misses in Nov 12, seed 901. June 15, seed 1701 **increased** realized carbon despite a lower surrogate-carbon candidate. Cost changes were also mixed.

These dates were all previously explored. Treat this as a **development/ablation result, not a prospective generalization test**. The task-level routing effects are causal under these deterministic paired-simulator experiments only under their simulator assumptions, not proof of deployment safety or physical calibration.

## Research consequence

**The current aggregate predicted count + total tardiness cap is not a reliable SLA safeguard**: per-job predicted completion can worsen while aggregate objectives stay flat, and altered decisions change future queue dynamics. A unit-level no-later predicted completion constraint is being developed as an independent, more conservative ablation. It also cannot guarantee realized SLA due to future arrivals and shared capacity. The core remaining scientific challenge is predicting the full simulator's facility/battery/cooling marginal carbon, and reducing emissions without unacceptable realized SLA loss.

Never advertise the current selector as 'SLA-safe' or claim three-objective dominance. Both favorable and unfavorable runs must remain in the table, with any new comparison done against the original With-Transit baseline and non-queue ablations under matched admissions and fixed GA request budget.
