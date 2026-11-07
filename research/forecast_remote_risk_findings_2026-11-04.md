# Queue prediction false-safe risk: route-stratified exploratory evidence

Source: successful GitHub Actions run https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41822550674

Scenario: June 15 workload, random seed 733, 5% nominal CPU capacity, 291 completed tasks per policy; three policies audited under an identical admission cohort. Forecast labels are made at dispatch using current observable state; realized starts and SLA outcomes are checked after completion.

| Policy | Predicted-safe tasks | False-safe tasks | Local false-safe / predicted-safe | Remote false-safe / predicted-safe |
|---|---:|---:|---:|---:|
| Queue-NSGA-II | 288 | 21 | 0 / 91 (0%) | 21 / 197 (10.66%) |
| Carbon-Guard | 250 | 39 | 4 / 83 (4.82%) | 35 / 167 (20.96%) |
| Carbon-SLA-Guard | 282 | 38 | 0 / 89 (0%) | 38 / 193 (19.69%) |

These are *conditional error rates*, not failure rates over every task. The remote and local groups arise from each policy's selected routes, so they have different populations and cannot support a causal claim that remote routing alone caused the misses.

Notable diagnostic: on Queue-NSGA-II, 12 of 164 predicted-safe tasks with at least 60 minutes slack were still false-safe; on Carbon-Guard, 26 of 120; on Carbon-SLA-Guard, 25 of 156. Fixed short buffers are unlikely to explain every error.

**Research decision:** prioritize current in-transit arrivals and queue/transfer timing alignment and inspect the actual/forecast start residual distribution. Develop a prospective route-conditioned uncertainty model using only *prior-date* residuals. Keep a new date unobserved for final testing; do not claim the current June 15 retrospective rates predict other dates.

**Validity guard:** The original forecast row schema used job name but no admission timestamp. The updated branch adds `arrival_utc` and identifies each forecast by date, seed, policy, task arrival and job name to support repeated names at different arrivals. The identity fix itself still requires full CI validation.

This environment models independent-job multi-DC placement, not DAG precedence scheduling. The above is descriptive simulator evidence, not validated physical causation or method novelty.
