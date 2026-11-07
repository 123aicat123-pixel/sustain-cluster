# Frozen development ablation: single-search lagged-PUE front taskwise gate

**Declared 2026-11-07, before any results.** This experiment repurposes an existing deterministic cached-final-Pareto-front selection rule from `research/transit_front_carbon.py`; it does NOT introduce a new risk theorem or an original scheduling algorithm.

## Hypothesis

The double-NSGA-II shadow reference reduced realized SLA misses in all four explored high-congestion seed pairs relative to ungated PUE, but required about twice the computational budget and still regressed against Indexed in 3/4 cases. A lower-cost alternative is to apply the already existing cached-front selection rule to `QueueAwareLaggedPUE`: among the final NSGA-II Pareto-front chromosomes, accept a candidate only when its PUE-weighted *proxy* carbon is strictly lower than the knee choice, and every task's predicted completion is no later than the knee choice. The rule evaluates already cached optimizer candidates and uses zero additional GA evaluation requests.

The rule compares alternatives **against PUE-knee**, not against the PUE-blind `queue_nsga2_indexed_transit`. Thus it is NOT a guarantee of no added SLA misses versus that baseline. Shared-queue spillovers and future arrivals may still invalidate predicted nonlater finishes.

## Fixed exploratory test

Use Jan 20 and Apr 15 at synthetic CPU scale 0.05; seeds 901 and 1701, 16 admission steps plus 112 drains; four policies per seed:
1. `queue_nsga2_indexed_transit` (PUE-blind comparator)
2. `queue_nsga2_lagged_pue` (ungated candidate)
3. `queue_nsga2_lagged_pue_front_taskwise` (new **one-search** front ablation)
4. `queue_nsga2_lagged_pue_shadow_guard` (prior **two-search** guard)

16 policy simulations. These dates were already used during algorithm development, and are NOT independent held-out generalization.

All methods retain the same candidate action sets, in-transit queue predictor, per-search NSGA-II population 16 × generations 8 and fixed seeds. The front-only candidate has **exactly the same** total optimizer evaluation requests as ungated PUE / indexed. The shadow reference has **twice** those requests; comparison must report P95 time and request totals. There is no tuning of front thresholds on the Jan/Apr outcomes.

## Hard data gates, and what would falsify the hypothesis

Require complete matched task cohorts, zero fallback, lifecycle conservation, paired-task analysis for each candidate, finite cost/carbon, and consistent total optimizer requests. Archive any failed or censored runs. Report signed deltas in actual **facility-plus-transmission carbon**, SLA misses, planner P95, front interventions, changed destinations, and SLA rescues/harm. Do not require a win; a no-op or regression is a legitimate outcome.

If no non-knee cached-front chromosomes satisfy the taskwise constraint, the new method will be observationally identical to the PUE candidate. Even with front interventions, lower PUE-proxy carbon need not improve simulator carbon, and predicted no-later completion does not guarantee real-world task safety.

This is **engineering/method diagnostic only**. A defensible SCI claim still requires a distinct action-conditional marginal facility-carbon model, a principled bounded-risk mechanism, and independent workload validation.
