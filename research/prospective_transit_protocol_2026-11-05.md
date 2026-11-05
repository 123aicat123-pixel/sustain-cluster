# Frozen prospective calendar/stress evaluation protocol (2026-11-05)

**Status: PRE-RESULT PROTOCOL.** This document was written before checking results on the following dates/scenarios. Commit SHA and future CI run must be recorded before looking at performance outputs.

## Scope and hypotheses
SustainCluster presently supports independent-job routing across datacenters, NOT DAG workflow precedence. We will test the hypothesis that `queue_nsga2_with_transit` improves realized SLA misses and dispatch-time queue-start forecast accuracy compared with `queue_nsga2` on new Alibaba workload dates, while measuring the cost/carbon tradeoff without filtering unfavorable cases. `queue_nsga2_no_queue` provides an action-set-matched negative-model ablation.

## Frozen experiment plan
- **New workload calendar days** (2020 Alibaba trace mapped into simulator calendar): Feb 12, May 19 and Nov 12. These three dates were not used for the June/August/September/October prototype selection described in prior notes.
- **Independent PRNG conditions** within each date: seeds **901** and **1701**. Seeds on the same date share the arrival cohort and are not independent trace datasets.
- **CPU capacity factor**: 0.05 and 0.10 of each original configured datacenter's CPU count (GPU/memory settings unchanged). Do **not** compare raw facility emissions across different capacity factors as if the physical plant were identical.
- **Three algorithms** with identical spatial action set: `queue_nsga2_no_queue`, `queue_nsga2`, `queue_nsga2_with_transit`. NSGA-II search population 16, generations 8, compromise weights 0.1/0.1/0.8 for queue-aware algorithms; No-Queue shares implementation and budget.
- 16 x 15-minute admission steps; 112 drain steps. Fixed per-task v2 transfer treatment, same candidate DC set, seed, current inputs, and simulator accounting across policies.
- 6 date-capacity scenarios × 2 seed conditions × 3 policies = **36 full simulator runs**. All attempted runs, negative and null results retained.
- No tuning thresholds, evolutionary population, weights, predictor parameters, or resource capacity in response to these results.

## Validation and comparison gates
1. Require task count, calendar start, capacity scale and physical accounting invariants to be independently consistent for every run.
2. Require all candidate policies to finish the same admitted workload with zero fallback and zero unfinished dispatched tasks. If not, mark the particular seed/scenario **CENSORED** and do not rank by completed-task SLA/cost/carbon.
3. For eligible runs, verify exact task-level alignment keyed by (seed, arrival_utc, job_name), immutable duration/deadline/origin, then compute paired SLA rescues and harms and confirm the counts reconcile with reported misses.
4. Report physical total carbon kg, cost USD, missed deadlines, queue start MAE, P95 error and false-safe SLA counts, plus algorithm run time *when instrumented*. No data points will be removed as outliers solely for being unfavorable.
5. Treat the calendar day as the unit of workload diversity. No per-task significance tests; scenario-level uncertainty needs more dates for publication claims.
6. Dates sampled and analyzed here become **explored** once outcomes are seen. Any later final confirmatory evaluation requires different untouched calendar partitions and an explicit protocol freeze.

## Interpretation caveats
The simulator's cost/carbon includes non-task and cooling/battery effects; current optimizer fitness is only a task-level surrogate. Prediction starts are known-time forecasts and future arrivals are unobservable. The algorithm corrects a specific omission in an existing adapted predictor; originality and real-world validity are not established. Do not claim a three-objective Pareto improvement when emissions worsen, or conflate simulator correctness with a peer-reviewed science result.
