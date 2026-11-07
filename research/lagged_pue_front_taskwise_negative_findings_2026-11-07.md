# Single-search PUE cached-front taskwise pilot: mixed/negative results (2026-11-07)

**Source:** https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42376665505 (two successful GitHub Actions matrix jobs; four matched seed-policy cohorts). Frozen pre-result protocol: `research/lagged_pue_single_search_front_protocol_2026-11-07.md`.

The policy `queue_nsga2_lagged_pue_front_taskwise` chooses among **already evaluated** candidates on the PUE-adjusted NSGA-II final front. It is NOT compared for per-task non-later completion against a PUE-blind baseline, only against the PUE knee solution. The study dates Jan 20 / Apr 15, 5% synthetic CPU, seeds 901/1701, were used during development. This is independent-job placement, not DAG workflow scheduling.

All differences below are **single-search front MINUS Indexed-Transit**, except where explicitly labeled otherwise. This is actual simulator facility-plus-transmission carbon, not an action-calibrated marginal-carbon measurement.

| Workload | Seed | Completed tasks per policy | Final front interventions | SLA misses Δ vs Indexed | Carbon Δ kg vs Indexed | SLA Δ vs unguarded PUE | Carbon Δ kg vs unguarded PUE | Front P95 ms | Indexed P95 ms | Shadow P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Jan 20, CPU 5% | 901 | 291 | 2 | 0 | +55.548 | -9 | -1.447 | 269.06 | 285.19 | 516.57 |
| Jan 20, CPU 5% | 1701 | 291 | 0 | +3 | -12.210 | 0 | 0 | 257.28 | 259.73 | 528.61 |
| Apr 15, CPU 5% | 901 | 682 | 1 | +15 | -46.578 | +4 | -57.469 | 500.21 | 496.48 | 1025.64 |
| Apr 15, CPU 5% | 1701 | 682 | 1 | +15 | -29.231 | +3 | +11.425 | 487.69 | 494.80 | 947.19 |

Front-Taskwise used 6,400 NSGA-II evaluation **requests** versus 12,800 for the previously introduced two-search shadow reference, but timing on shared GitHub runners is not hardware-controlled. It is an experimental compute-budget improvement, not a demonstrated universal P95 speedup.

**Key falsifications:**
1. The current PUE-front taskwise gate does not yield consistent jointly nonworse actual carbon and SLA: **0/4 paired seeds**.
2. The candidate barely intervened (0–2 changes over the complete scenario), so the unchanged PUE-knee solutions and shared-queue spillovers remain a concern.
3. Even when predicted batch completion is non-later, realized SLA may be harmed by changes to currently queued or in-transit tasks, and by future workload arrivals. It is not a safety theorem.
4. Lower PUE surrogate carbon is not enough to guarantee lower actual simulated facility carbon.

## Next discriminating test: observable queue externalities

Under a **single** NSGA-II search, test a new additive surrogate tardiness term for known, already-admitted pending tasks whose predicted start/finish is delayed by the newly assigned candidate batch. Compare with a no-new-dispatch baseline using ONLY current queue state, running-task finishes and observed in-transit commitments. This is a *queue predictor* experiment, not a causal estimate of actual service outcomes or a risk proof.

Predeclare:
- Exact same PUE proxy, candidate routing action spaces, NSGA-II search parameters, and dates/seed controls.
- Record extra queue-projection calls and wall time separately from NSGA-II evaluation requests; an equal search budget is not equal CPU cost.
- Keep the previous Indexed, PUE and single-search-front methods as controls.
- New risk penalty need not improve facility carbon; select next research direction according to real simulator outcomes, not surrogate scores.
- Dates for method development are already explored; a later truly untouched test set is still needed.
