# Indexed queue counterbalanced validation: interpretation guide (2026-11-06)

## State of evidence

The earlier indexed-membership two-seed June 15 simulation passed and showed negative Indexed-minus-Legacy P95 deltas under a fixed Legacy-first ordering. This is one calendar date; it does not establish robust speedup.

Run https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42155809537 failed in the **pre-simulation unit test**, not due to a simulated algorithm regression. The test fixture changed P95 from 10 to 9 ms without also reducing P50, violating the valid percentile condition P50 <= P95. Corrected test fixture on commit `b431c12da45ca9ceed01f7ba21a885da59472feb`; avoid treating the failed run as negative scheduling evidence.

The corrected order-balanced experiment on the other previously explored dates tests whether timing direction persists when policy invocation is reversed. The experiment and audits must complete successfully before any cross-date conclusion.

## Preventing favorable-order selection

The source module `research/indexed_counterbalanced_summary.py` preserves both directions (`forward` Legacy->Indexed and `reverse` Indexed->Legacy) for every date/capacity/seed combination. It validates absolute P95 and signed delta agreement, marks each metric `faster_both_orders`, `slower_both_orders`, `equal_both_orders`, or `mixed_or_zero`, and calculates the mean *only across the two recorded orders for the same seed*. It does not pool tasks as independent replicates or compute p-values.

A workflow update runs tests for the summary contract and writes a per-scenario JSON summary alongside the already archived raw task- and planner-level data. Each matrix job is a separate artifact; a later joint summary must read all scenarios rather than silently presenting only the first successful one.

## Scientific caveats

- Both counterbalanced dates were examined during development; this is a timing robustness check, not unseen test generalization.
- A positive Indexed implementation delta is an engineering observation, not a new queue-aware scheduling algorithm.
- `perf_counter` wall time on runner hardware can shift with host contention, package setup, order and warm-up, and does not measure carbon emissions consumed by the planner itself.
- The simulator models independent jobs and no DAG task dependencies. The paper should not be described as dependency-aware workflow scheduling.
- Keep positive, negative, zero and censored cases in the results, with raw run links and exact commit SHA for reproducibility.
