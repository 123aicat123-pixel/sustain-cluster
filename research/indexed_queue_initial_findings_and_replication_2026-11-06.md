# Indexed queue lookup optimization — initial positive result and counterbalanced replication protocol

**Evidence:** successful indexed policy ablation workflow:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42021739696

**Scope:** cloud multi-datacenter *independent job* assignment, not dependency-aware DAG workflow scheduling.

## Verified initial behavior preservation and observed compute savings

Alibaba June 15, 5% synthetic CPU capacity, 16 admission steps + 112 drain steps; policies were legacy `queue_nsga2_with_transit` and `queue_nsga2_indexed_transit`. All runs completed matched cohorts with zero fallbacks and identical task destinations, start timestamps, finish timestamps, missed-deadline counts, physical simulator cost/carbon and forecast MAE.

| Seed | Jobs per policy | Indexed-minus-legacy planner P95 (ms) | Indexed-minus-legacy planner mean ms/task | Indexed-minus-legacy cumulative projection time (s) |
|---|---:|---:|---:|---:|
| 901 | 291 | -19.911 | -0.3211 | -0.07108 |
| 1701 | 291 | -10.853 | -0.1301 | -0.04243 |

150 randomized FIFO/in-transit predictor comparisons and error-path checks also passed. The experimental change builds a membership set once per projection instead of calling `dict(arrivals)` for each started task. No changes to search budget, legal actions, future signals, physical simulation equations, or stochastic optimizer.

**Important caveat:** These two seeds share one arrival date, and the legacy policy always ran before indexed. This is promising low-level engineering, **not** established general speedup or a scheduling science novelty claim.

## Frozen counterbalanced replication

Follow-up workflow `.github/workflows/research-indexed-counterbalanced.yml` runs two other **already explored**, distinct calendar/resource combinations:
- May 19 at 5% CPU scale;
- November 12 at 10% CPU scale.

Seeds 901 and 1701 for each. For each scenario, run both `Legacy -> Indexed` and `Indexed -> Legacy`. This generates 2 dates × 2 seeds × 2 policies × 2 run orders = 16 simulator policy runs, subject to complete drains and successful CI. This is not an untouched blind holdout.

Strict audit `research/indexed_order_audit.py` rejects censored simulations, fallback routing, mismatched evaluation budgets, and any task-level destination, start time, finish time, or SLA disagreement across both policies and run orders. The raw report preserves the signed P95, ms/task, and projection-seconds difference in **each order**, without choosing the favorable ordering.

**Interpretation gate:** if speed reductions change sign under reverse order or other workloads, do not claim robust speedup. Consider steady-state microbenchmarking with warm-up, order randomization, and process/CPU control. The measured wall time does not directly quantify extra electricity consumption by the scheduler, and it is separate from simulated datacenter energy.

No changes to `main` are required for this development experiment.
