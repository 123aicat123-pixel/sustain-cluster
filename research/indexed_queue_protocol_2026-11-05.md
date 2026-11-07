# Indexed membership ablation: preregistered exploratory implementation check

**Date:** 2026-11-05. **Status:** code committed; outcome CI pending.

## Motivation and exact change

The original `predict_starts` rebuilds `dict(arrivals)` at each projected task start to check whether the started task belongs to the newly arriving batch. This yields repeated allocations inside the queue projection hot path.

The controlled version keeps the legacy predictor selectable with `indexed_membership=False` and adds `indexed_membership=True`, which constructs a task-membership set once per queue projection and reuses it at each projected start. It does NOT change candidate data centers, queue order, resource release, in-transit treatment, transfer delays, fitness objectives, genetic budget or search RNG. It also does not promise measurable performance improvement.

The new `queue_nsga2_indexed_transit` class differs from the existing `queue_nsga2_with_transit` only by the above flag. Both are independent-job routing methods, **not** DAG scheduling.

## Frozen comparisons before evaluating outcomes

Run workflow `.github/workflows/research-indexed-queue.yml` (committed before simulated outcomes). The two policies share:
- Alibaba June 15 trace admission window, 16 admission + 112 drain steps.
- Artificial CPU capacity factor 0.05.
- Seeds 901 and 1701; these are correlated variants of **one** calendar workload and not independent test traces.
- NSGA-II population 16, generations 8, compromise weights 0.1/0.1/0.8.

The workflow includes 150 randomized FIFO + in-transit predictor equality cases, duplicate-in-transit and capacity errors, and a paired full-simulation audit. Full ranking is rejected if tasks are unfinished, fallback occurs, search budgets differ, or any task-level dispatch, start, finish or SLA outcomes change. Physical cost/carbon and forecast metrics must also match exactly.

## What to report

For each seed, record full planner p95 and total milliseconds per dispatched task, as well as cumulative projection call seconds; all deltas are **Indexed minus Legacy**. Preserve positive, negative and zero time differences. A decrease in projection compute does not automatically imply a decrease in overall planning time.

These GitHub runner times lack randomized process order, CPU pinning and warm-up, so even a successful comparison is an exploratory implementation optimization, not a statistically established speedup. The date has already been used for algorithm development and is not a blind holdout.

## Publication gate

Only consider this implementation change as a robustness/efficiency detail after all behavior-preservation audits pass and repeated timing measurements on diverse workloads agree. Do not claim a novel scheduling method, real energy savings from the host CPU, or guaranteed improvements from these tests.
