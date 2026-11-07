# First controlled single-route experiment: initial full-simulator findings

**2026-11-05**. **Exploratory, previously explored June 15 and November 12 task traces; NOT a new untouched validation cohort.** Simulator routes *independent jobs*, not DAG workflows.

**Frozen pre-result intervention protocol:** `research/single_route_intervention_protocol_2026-11-05.md`; initial commit `c0402ce76b6025ec3836dfaf8874bdbb81291522`. **Real successful GitHub Actions run:** https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42019359382 (2/2 jobs succeeded, 12/12 policy × seed × date full simulator runs completed, all task cohorts 100% drained, no fallback). Preserve its `single-route-june15_05` and `single-route-nov12_05` raw artifacts.

The fixed intervention arms are `probe_control` (no change), `probe_low_ci`, `probe_high_ci`. All use the same deterministic round-robin base selector and legal action path. Only one task in the first eligible dispatch batch is explicitly rerouted in each treatment. **Important terminology:** the observed selector uses **current ci_manager source/grid CI**, *not* battery-adjusted effective CI `bat_avg_CI`. The latter is part of actual facility carbon accounting. Do not silently rewrite the frozen scheme after results.

## Realized differences versus the unmodified round-robin arm

A negative total carbon delta means lower final simulator-reported carbon for the entire 128-step horizon.

| Workload date | Seed | Treatment | Control SLA misses | Treatment SLA misses | Facility CO2 delta kg | Transfer CO2 delta kg | Total CO2 delta kg |
|---|---:|---|---:|---:|---:|---:|---:|
| Jun 15 | 901 | low source CI | 25 | 26 | -0.111686 | +0.000191 | -0.111495 |
| Jun 15 | 901 | high source CI | 25 | 25 | +0.338641 | -0.416701 | -0.078060 |
| Jun 15 | 1701 | low source CI | 25 | 25 | -0.709382 | -0.001446 | -0.710828 |
| Jun 15 | 1701 | high source CI | 25 | 25 | +1.017079 | +0.000000 | +1.017079 |
| Nov 12 | 901 | low source CI | 97 | 97 | -0.020311 | +0.000000 | -0.020311 |
| Nov 12 | 901 | high source CI | 97 | 97 | +1.586095 | -0.000482 | +1.585613 |
| Nov 12 | 1701 | low source CI | 98 | 98 | -0.216018 | +0.000000 | -0.216018 |
| Nov 12 | 1701 | high source CI | 98 | 98 | +1.318741 | +0.000240 | +1.318981 |

These are small **total downstream simulator intervention effects**, not calibrated task-marginal energy coefficients. Their numerical scale relative to whole-facility emissions in the thousands of kilograms shows why optimizing a raw 6W/core proxy without controlled measurements can be misleading.

## Facility IT/HVAC decomposition

Exact paired DC/time-step attribution (15-minute cells, unchanged within-cell effective CI):

- Jun 15 seed 1701, low CI: IT effect **-0.141714 kg**, HVAC effect **-0.567668 kg**. HVAC is most of the facility reduction **-0.709382 kg**.
- Nov 12 seed 901, high CI: IT effect **+0.290727 kg**, HVAC effect **+1.295367 kg**. HVAC is most of the facility increase **+1.586095 kg**.
- Jun 15 seed 901, high CI: IT **+0.196194 kg**, HVAC **+0.142447 kg**, but transmission **-0.416701 kg**, making *total* emissions decline.
- Relative source CI direction does not guarantee actual *total* carbon direction, and a lower CI route can increase real SLA misses (Jun 15, seed 901: 25→26).

## Pending reproducibility gate

The initial workflow verified equal task counts, same selected target metadata, fully drained cohorts, 128 × five center telemetry and all facility power-carbon sums. It did **not yet independently prove that exactly one task's realized final destination changed**, rather than merely one intervention action. An additional route-by-route task audit and regression tests were added later in `research/single_route_intervention_audit.py`; their newer CI must pass before claiming exact matched task-level single-route equivalence. This document therefore makes only the narrower claim verified in the original successful run: exactly one explicit adapter action was altered at the first eligible batch.

## Next research criterion

The correct next baseline is an *action-conditioned* surrogate predicting total facility+transmission carbon shifts under shared queue and cooling effects using past/intervention training observations, NOT a second whole-plant future-carbon regressor. This 2-date intervention dataset is for feasibility and development only. Do not treat its eight treatment comparisons as independent workload dates. Freeze any learned policy and evaluate new dates, capacities, sensitivity and full SLA/cost/carbon tradeoffs separately before publication claims.
