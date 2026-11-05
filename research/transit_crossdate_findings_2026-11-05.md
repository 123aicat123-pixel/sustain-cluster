# In-transit queue projection: cross-calendar outcome audit (2026-11-05)

**Scope:** multi-datacenter independent-job placement, not dependency-aware DAG scheduling.
**Evidence:** successfully completed GitHub Actions run:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41838645508
Validated complete matched cohorts, no unfinished dispatched tasks and no fallback for both policies on August 15 (717 jobs/run) and October 1 (707 jobs/run), seeds 501 and 733. Same resource stress (5% CPU), 16 admission steps plus 112 drain steps. The dates and policies have already been inspected: **not untouched holdouts**.

| Trace | Seed | Baseline SLA misses | Transit-aware SLA misses | Baseline start MAE min | Transit start MAE min | Baseline cost USD | Transit cost USD | Baseline carbon kg | Transit carbon kg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Aug 15 | 501 | 53 | 41 | 2.3431 | 0.3766 | 954.093 | 952.084 | 2994.789 | 2996.645 |
| Aug 15 | 733 | 43 | 41 | 2.5105 | 0.1464 | 1065.145 | 1064.513 | 3210.054 | 3220.011 |
| Oct 1 | 501 | 98 | 56 | 11.6266 | 0.4880 | 1145.530 | 1117.812 | 3114.955 | 3165.171 |
| Oct 1 | 733 | 61 | 28 | 6.8741 | 0.3395 | 1352.322 | 1356.504 | 3037.620 | 3081.988 |

Across these four *seeded scenarios* the SLA miss count is 255 vs 166 (-89, 34.90% fewer), and the reduction has the same direction in each scenario. Every scenario also has **higher realized carbon emissions** with the transit-aware policy (differences: +1.856, +9.957, +50.215, +44.368 kg). Cost effects have mixed signs. Summing miss counts across scenarios is descriptive and does not create independent experimental replicates: seeds within each date share admission cohorts.

## Supported and unsupported conclusions

- Supported within these simulations: modeling currently observable *already-in-transit* tasks reduces optimistic start-time errors and changes decisions in ways associated with lower realized missed-deadline counts.
- Unsupported: three-objective Pareto dominance, significant improvements across independent dates, real-world facility-carbon calibration, or that this is an original peer-reviewed scheduling mechanism.
- Remaining risks: upstream task-in-transit ordering and 15-min discretization, unobserved future arrivals, the simplistic marginal-carbon surrogate (6 W/core) versus full plant/cooling/battery accounting, and policy-dependent routing distribution.
- GitHub Actions tested the physical simulator and cohort invariants; the inference is still exploratory.

## Next predeclared experiment

1. Keep this policy and baseline fixed. Verify reproducibility and compare with No-Queue, SLA-Carbon and a matching transit-aware carbon-guard ablation under the same legal candidate set and genetic search budget.
2. Choose at least **three new** calendar admission dates from the valid trace where the exact cohorts were not used to develop this candidate; document the date choice *before* results and do not retune on the evaluation dates.
3. Vary CPU-capacity stress (e.g., 5%, 10%, 20%); never mix capacity-dependent absolute emissions as if identical facilities. Admit the same trace cohort and require all policies to finish or mark comparisons censored.
4. Record task-level paired misses, start-time residuals, planner overhead, total carbon/cost and scenario-level uncertainty. Report negative results.
5. Explore actual marginal facility-energy modeling only with physically justified, past-observable inputs. A Carbon-Guard cannot be called carbon-safe or SLA-safe merely because a proxy constraint is satisfied.

## Regression observation

Recent research CI failed because `research/queue_prediction_audit.py` now exports the immutable `arrival_utc` field but a dummy task fixture lacked `arrival_time` (not a simulator failure). The fixture was corrected on the research branch on 2026-11-05; confirmation from subsequent CI is a separate verification gate.
