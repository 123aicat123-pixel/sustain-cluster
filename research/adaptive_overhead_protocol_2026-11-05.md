# Adaptive transit planner overhead: exploratory protocol (2026-11-05)

**Scope:** independent-job multi-datacenter placement under a common SustainCluster simulator. This is *not* DAG workflow scheduling, independent held-out testing, or evidence of new algorithmic novelty.

## Research question

Can `queue_nsga2_adaptive_transit` reduce decision-time computing overhead relative to `queue_nsga2_with_transit` without materially deteriorating full-simulator SLA, facility-plus-transfer carbon, or cost?

The adaptive method already exists in `research/queue_aware_nsga2.py`; this protocol introduces no post-hoc tuning or new gate.

## Locked exploratory run

Workflow: `.github/workflows/research-adaptive-transit.yml`.
- Dates: June 15 at synthetic CPU scale 0.05; May 19 at scale 0.10.
- Seeds: 901, 1701 for each date/capacity; **seeds are not independent calendar workloads**.
- Policies: queue_nsga2, queue_nsga2_with_transit, queue_nsga2_adaptive_transit.
- Dispatch: 16 admission and 112 drain steps, same action legality and fixed NSGA-II evaluation requests.
- The workload dates were previously explored and therefore cannot be described as untouched test dates.

## Comparability and censoring

The new `research/adaptive_overhead_audit.py` groups rows by date, capacity and seed and requires complete, fallback-free dispatch cohorts, lifecycle conservation, equal admitted counts, timing coverage and matched GA evaluation requests. It checks adaptive projection counters; task-level matching still comes from the separate paired-comparison audit in the workflow.

For each matched scenario the new report preserves differences as **Adaptive MINUS With-Transit**. Positive SLA-miss, carbon and cost differences represent worse realized outcomes; positive timing differences represent slower adaptive execution. It never filters out unfavorable or zero-effect comparisons.

## Analysis caveats

- Planner timing uses Python `perf_counter()` on shared GitHub-hosted runner jobs and excludes simulator stepping, trace loading and audit. These readings are not measured physical scheduler energy.
- The timing benchmark has no warm-up randomization or repeated independent hosts. Report absolute millisecond values, not universal speedup.
- The fraction of saved full projections does not automatically equal the reduction in end-to-end planning time.
- Capacity scaling changes the simulated plant. Never pool absolute kg/USD across 5% and 10% as though the physical system is identical.
- Audit success establishes data consistency, not a statistically significant or generally better algorithm.
- Retain all CI logs and artifacts; a failed/censored scenario is a result, not a reason to select favorable seeds.

**Decision hinge:** only if this development study finds compute savings without unacceptable outcome regressions should the implementation be frozen and tested on separate, predeclared workloads and more diverse capacity/arrival windows.
