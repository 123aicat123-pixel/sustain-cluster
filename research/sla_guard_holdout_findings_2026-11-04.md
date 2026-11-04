# Cross-calendar falsification of proxy SLA-guard (2026-11-04)

**Status: reproducible exploratory negative result; no novelty or superiority claim.**

Source: successfully completed full-simulator GitHub Actions workflow
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41814814015

The holdout protocol was specified in `research/sla_guard_protocol.md`. The workflow reported 112 unit/contract tests passed; all 16 policy runs (2 dates × 2 seeds × 4 policies) completed their admitted tasks without fallback, pending work, or in-transit work. June 15 had 291 tasks per run; October 1 had 707 tasks per run. Dates differ in admitted trace cohort; seeds within one date are correlated and cannot substitute for distinct dates.

## Real outcomes: Queue-NSGA-II versus Carbon-SLA-Guard

| Admission date | Seed | Queue SLA misses | SLA-Guard misses | Queue carbon kg | SLA-Guard carbon kg | Queue cost USD | SLA-Guard cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| June 15 | 501 | 54 | 54 | 3149.023 | 3149.023 | 1125.097 | 1125.097 |
| June 15 | 733 | 24 | 46 | 3070.456 | 3074.676 | 1136.220 | 1157.581 |
| October 1 | 501 | 98 | 98 | 3114.955 | 3114.955 | 1145.530 | 1145.530 |
| October 1 | 733 | 61 | 107 | 3037.620 | 3053.377 | 1352.322 | 1365.503 |

Realized SLA misses and physical accounting come from the workflow's independent task audit and scenario-level guard-outcome analyzer.

The proposed safeguard left the original policy outcomes unchanged in two scenarios. In the other two scenarios it increased misses by 22 and 46 and worsened both emissions and cost. Thus the prototype **fails its original no-extra-SLA hypothesis and cannot be claimed SLA-safe or consistently carbon improving**.

Mechanistic caution: the post-search gate compares *batch-level predicted tardiness* between an already-optimized decision and a heuristic fallback. Even if the estimated current-batch tardiness does not rise, queues and future arrivals can change subsequent task outcomes. The predictor also lacks a calibrated facility marginal-emissions response. A predicted *total tardiness* constraint is not equivalent to a guarantee about the count of realized deadline misses.

## Research decision

- Retain the results and the algorithm as an explicit negative-result ablation; do **not** tune on these two dates and call them untouched holdouts again.
- Stop claiming Carbon-SLA-Guard is a viable improved algorithm until a new prospective protocol verifies it.
- Next hypothesis: compare individually predicted miss probabilities or safety margins using **past-observable** queue-start forecast errors. Evaluate a calibrated, risk-budgeted rule against *both* Queue-NSGA-II and the lower-cost No-Queue version with exactly matched action sets and budgets.
- Separate power-model/physical energy calibration from optimization improvements, and report measured carbon, cost, missed deadlines, prediction errors, and per-decision runtime.
- Hold out at least one *new* calendar date and a new resource-stress scenario before adding any performance claim.
- This simulator currently schedules independent jobs; no DAG edges/precedence constraints have been implemented.

The successful workflow validates completion and assertions, **not** generalization, physical realism, or SCI publishability.
