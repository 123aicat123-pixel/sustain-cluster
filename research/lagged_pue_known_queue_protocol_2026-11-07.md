# Pre-result protocol: single-search PUE with known-queue externality objective

Declared 2026-11-07 **before any simulator outcomes**. This is a falsifiable engineering/method hypothesis, NOT established SCI novelty, a causal estimate of physical emissions, nor a formal SLA risk guarantee. The simulator handles independent cloud tasks, not DAG workflows.

## Motivating negative evidence

The Front-Taskwise selector had **0/4** pairwise jointly nonworse real-simulator SLA/carbon results in the two explored, high-congestion January 20 and April 15 workloads (5% simulated CPU). A separate task-level audit showed some non-rerouted tasks changed their observed start times and SLA outcomes. The observational association suggests shared queue load but is not causal identification.

## Locked intervention

Baseline `queue_nsga2_lagged_pue` continues to optimize its cost, lagged average-PUE-weighted carbon proxy, and predicted tardiness of NEW batch tasks.

New ablation `queue_nsga2_lagged_pue_known_queue` uses the **same** population, generations, search weights (0.1,0.1,0.8), random seeds, candidate data centers, queue predictor, observed electricity and facility-PUE information, and **one** NSGA-II per batch. Only its third fitness objective adds:

`known_queue_tardiness = sum_{already_committed_tasks} max(0, tardiness_with_proposed_batch - tardiness_no_new_batch)`.

Both forecasts use ONLY currently known pending/running and already-in-transit tasks, their currently known finish and deadline timestamps, and the hypothetical newly admitted batch. No unseen future workload arrivals or future facility/carbon signal. The coefficient of the added tardiness is fixed at **1.0 minute per minute** (no tuning on validation results).

To reduce unnecessary duplicate work, reference (no-new-action) known-queue projections are memoized **only within one nonempty dispatch decision**, never across changed environment states. Record extra counterfactual queue calls and cumulative seconds, plus NSGA-II evaluation request count and P95 planning time. Equal NSGA-II requests **do not** mean equal computational work; this model adds queue projections.

## Fixed development experiment

Run Jan 20 and Apr 15 at 5% synthetic CPU, seeds 901 and 1701, 16 admission + 112 drain steps. Compare:
1. `queue_nsga2_indexed_transit` (PUE-blind baseline);
2. `queue_nsga2_lagged_pue` (existing PUE baseline);
3. `queue_nsga2_lagged_pue_known_queue` (new single-search objective).

Total **12 policy simulation runs**. All dates/seeds were previously explored, and MUST NOT be presented as untouched generalization or independent-sample statistics.

Eligibility: fully completed matched task cohort, no fallbacks, lifecycle conservation, equal per-search optimizer requests and no second shadow optimizer. Report every signed delta of actual simulator facility+transmission carbon (kg), SLA misses, cost, planner P95, and nonzero externality evaluations. Retain failures, censoring and regressions. A zero intervention is a legitimate result.

## Decision criteria

If the added known-queue term has no real effect or worsens actual SLA/carbon, document a negative result; do NOT tune its coefficient after viewing this experiment. Even if it helps on these explored dates, test validity on genuinely unexamined dates before publication, then compare against stronger literature baselines.

Known predicted task start delays do **not** guarantee realized deadline outcomes under future arrivals. The previous lagged-average PUE proxy is **not** an action-conditioned calibrated marginal carbon model. Neither CPU energy for executing the scheduler nor physical cloud deployments are measured by this experiment.
