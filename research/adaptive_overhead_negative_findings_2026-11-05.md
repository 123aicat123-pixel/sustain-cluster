# Adaptive transit computation shortcut: complete exploratory negative result (2026-11-05)

**Source:** successful 2/2 GitHub Actions matrix jobs, 12 full simulation policy runs:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41999589732

**Status:** development analysis on already-explored workload dates. These are *independent jobs*, NOT DAG workflow scheduling. No claim of general speedup or novelty is authorized.

The three policies were Queue-NSGA-II, With-Transit and Adaptive-Transit, with seed 901/1701 at each date+capacity. All runs had complete matched admissions, zero fallback, and fully drained tasks. In all four Adaptive vs With-Transit comparisons, the task-level auditor found **zero destination/start/finish time differences**, with equal SLA misses, total realized carbon and total costs.

| Calendar, synthetic CPU | Seed | Tasks per policy | Adaptive skipped full transit projections | P95 timing delta (ms) | Mean planning time per task delta (ms) | SLA misses delta | Carbon delta (kg) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| June 15, 5% | 901 | 291 | 3014/6774 (44.49%) | +2.968 | -0.0440 | 0 | 0 |
| June 15, 5% | 1701 | 291 | 2537/6664 (38.07%) | +4.579 | +0.0588 | 0 | 0 |
| May 19, 10% | 901 | 417 | 5438/7580 (71.74%) | -0.094 | -0.0142 | 0 | 0 |
| May 19, 10% | 1701 | 417 | 4703/7263 (64.75%) | +0.201 | +0.0106 | 0 | 0 |

Differences are **Adaptive MINUS With-Transit**. Smaller decision time is better. Same fixed NSGA-II evaluation-request budget per matched policy (6400 for June 15, 6000 for May 19). Counter values count repeated objective calls and final auditing, not unique online decision epochs.

## Important falsifications

1. A high count of avoided full-transit projections is **not** evidence of a faster optimizer. P95 planning latency worsened on 3/4 cases; per-task timing worsened on 2/4.
2. Timing variation on Github-hosted shared runners is uncontrolled, so even small differences must not be interpreted as causal speedups or slowdowns.
3. Equal actual outcomes in four matched simulations do not establish a general equivalence theorem across workloads. The pure deterministic gate has unit tests, but the physical simulator may still show different behavior on new states.
4. The current project has not demonstrated significant whole-facility carbon reduction under the revised routing algorithms.

## Next falsifiable investigation: attribution, not threshold tuning

A subsequent code change adds observational `planner_projection_calls`,
`planner_projection_seconds`, and `adaptive_gate_seconds` counters to
the two transit-policy variants, and exports them through unified scenario
results. These counters are timed within each actual projection call, including
calls in repeated GA fitness evaluation and after-selection task auditing.

The extended adaptive audit now checks that projection accounting is
nonnegative, that gate time is no larger than projection time, and that
projection time is bounded by the total planner time.

**Interpretation:** if projection time is a small fraction of total planning
time, speedups should target other work (GA sorting, fitness bookkeeping,
candidate construction). If it dominates, investigate queue projection
repetition/caching without changing the legal action set or seed behavior.

This is instrumentation rather than an optimization. It has not yet been
independently verified to preserve outcomes by the new CI, and no timing
percentages are claimed until the run completes.
