# Cross-calendar validation: Carbon-Guard is not SLA-safe

Date audited: 2026-11-04. Source GitHub Actions successful run:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41796118426
Raw results artifact:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41796118426/artifacts/13305547951

## Experiment identity and validity

- Separate Alibaba task admission cohorts were verified for August 15 (717 unique admitted tasks) and September 1 (478 unique admitted tasks).
- Two seeded simulation conditions (137 and 271828) per date, with identical admission cohorts within the four policies compared in each seed/date.
- All 16 full-simulation policy runs completed every admitted task; no unresolved task and no fallback. The two seeds within a date are **not independent task-arrival cohorts**.
- Four policies: SLA-Carbon reference, Queue-NSGA-II No-Queue ablation, full Queue-NSGA-II, and Queue-NSGA-II Carbon-Guard.
- All results are simulator outcomes only, not a real-world causal energy validation. The selected dates were explored in validation, hence must not be reclassified as an untouched blind final test.

## Full versus Guard physical metrics

| Date | Seed | Full cost USD | Guard cost USD | Full carbon kg | Guard carbon kg | Full SLA misses | Guard SLA misses |
|---|---:|---:|---:|---:|---:|---:|---:|
| Aug 15 | 137 | 1264.465 | 1244.619 | 3035.860 | 3018.448 | 51 | 130 |
| Aug 15 | 271828 | 1098.443 | 1093.536 | 3564.289 | 3476.852 | 37 | 124 |
| Sep 1 | 137 | 945.792 | 946.255 | 2968.680 | 2967.720 | 0 | 0 |
| Sep 1 | 271828 | 925.715 | 929.420 | 2903.130 | 2897.198 | 1 | 2 |

SLA misses above computed from the independently task-paired confusion counts in the same run. Specifically, Aug 15 Full misses 51 and 37, while Guard misses 130 and 124; Sep 1 Full misses 0 and 1, Guard misses 0 and 2.

## Interpretation

Carbon-Guard reduced observed simulated carbon in all four conditions, but increased deadline violations by 79, 87, 0 and 1 respectively. Therefore its *proxy-carbon guard* is **not SLA-safe** and does not provide a three-objective Pareto improvement; the promising earlier 5%-CPU-capacity trial did not generalize. In September 1 trials it increased cost while reducing carbon slightly, as a tradeoff. Cost benefits on August 15 are also traded against substantial SLA harm.

Queue projection versus its matched No-Queue ablation is also highly condition-dependent: on September 1 they produced identical destinations, task starts, completions, cost and carbon; on August 15 queue projection changed decisions and outcomes.

A new implementation MUST avoid advertising a hard-SLA guarantee unless a formally valid decision rule can enforce it with calibrated uncertainty under unseen arrivals. Investigate risk-limited guard acceptance using predicted deadline misses versus SLA-Carbon and facility marginal-emissions calibration. Evaluate on fresh workload calendar dates and stress scales with full task completion, identical action sets and budgets, and per-decision timing. An alternative publishable contribution may be a negative-results / measurement-and-benchmarking study if no robust improvement is found.

## Audit boundary

This project is multi-datacenter independent-job placement, not DAG workflow scheduling; no precedence constraints or edge communication model have been implemented. GitHub Actions success checks experiment execution and the scripted invariants, not predictive calibration or novelty.
