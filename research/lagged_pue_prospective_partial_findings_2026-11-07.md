# Prospective Lagged-PUE: partial results and December site-index repair (2026-11-07)

**Frozen candidate:** `queue_nsga2_lagged_pue` versus `queue_nsga2_indexed_transit`. This evaluates independent-job placement, NOT DAG workflow scheduling, physical cloud deployments or causal marginal carbon.

Pre-result protocol: `research/lagged_pue_pilot_results_and_frozen_validation_2026-11-06.md`.
Original GitHub Actions run: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42188960403
Experiment under original commit `f05dc671744cdf6e786aa87992bbac886ce02d4d`.

## Outcome disposition — never silently discard failed jobs

Six date/capacity matrix cells were predeclared, 2 seeds × 3 policies = 6 simulator runs/cell, or 36 planned runs total.

- **Four successful cells (24 policy runs):** January 20 at simulated CPU 5% and 10%; April 15 at 5% and 10%. Every successful cell has 2 eligible paired seeds, matched task identities and full drain, no fallbacks, equal NSGA-II evaluation request budgets, and reconciled cost/carbon totals.
- **Two failed cells (12 planned runs not evaluated):** December 10 at 5% and 10%. Both aborted at `env.reset()` before the first scheduled task due to a **site trace initialization overflow** (`ValueError: low >= high` in `simulation.cluster_manager.reset`). This is not an algorithm carbon/SLA result. See the logs in the same Actions run.

## Signed paired findings — Candidate minus indexed reference

| Date | CPU | Seed | Carbon difference (kg) | SLA violation difference | Joint carbon/SLA nonworse |
|---|---:|---:|---:|---:|---|
| Jan 20 | 5% | 901 | +56.995215 | +9 | No |
| Jan 20 | 5% | 1701 | -12.209966 | +3 | No |
| Jan 20 | 10% | 901 | -1.275326 | 0 | Yes |
| Jan 20 | 10% | 1701 | -24.735859 | -2 | Yes |
| Apr 15 | 5% | 901 | +10.891163 | +11 | No |
| Apr 15 | 5% | 1701 | -40.655844 | +12 | No |
| Apr 15 | 10% | 901 | -8.073144 | -17 | Yes |
| Apr 15 | 10% | 1701 | -22.782066 | -15 | Yes |

The joint success proportion is **4/8 eligible pairs**, not 4/12 and not 8/8. Different seeds share arrival-date traces, so these are *not* 8 independent workload dates. 5%-capacity stress shows consistent SLA regression on both dates; 10% shows joint improvements on both dates. This is descriptive, not a significance/robustness claim.

**Key falsification:** a past-average facility PUE multiplier does not guarantee deadline-safe lower-carbon scheduling. Do not tune clipping or choose only the 10% cases after seeing outcomes. The stable across-capacity dual-benefit claim is false for the frozen prototype.

## Root cause of December failure

The upstream `train_SAC_agent.make_env` passes `int(month * 30.5 + day)` as `DatacenterClusterManager.init_day`, although that manager randomizes site trace day around a range clamped to 0..364. For Dec 10 the approximation becomes 376, so `low_day=max(0,376-7)=369` and `high_day=min(364,376+7)=364`; NumPy receives an empty random interval. Neither carbon fitness nor task queue prediction had run yet.

**Repair:** the research runner now calls `research.calendar_index_guard.correct_overflowed_init_day` *before* `env.reset()`. It preserves all prior in-range approximate site indices unchanged and for an overflowed requested calendar date uses the exact zero-based Gregorian day-of-year (Dec 10, 2023 = 343). The year is the simulator-local site trace year; the Alibaba job trace lookup still maps to 2020 as before. The result includes explicit `site_init_day_index` and `site_init_day_corrected` metadata.

**Critical caveat:** Dec 10 will be evaluated under its corrected site trace season, while original in-range dates retain upstream approximation. This does not make the index convention scientifically correct across all dates. Do not pool interpreted seasonal effects without a separate full calendar-index sensitivity experiment. Fixing it in the study runner does not silently modify upstream `main`.

Recovery workflow: `.github/workflows/research-lagged-pue-december-recovery.yml` runs **only** the two originally specified December cells with *unchanged* policies, seeds, CPU capacities, admissions, drains and all audit gates. Its 12 recovered policy simulations, if successful, must be reported together with the earlier 24. If December still fails or is censored, retain the failure; do not choose a replacement date after seeing other outcomes.

## Scientific decision

Keep the unchanged Lagged-PUE as a transparent **baseline/ablation**, not the final SCI contribution. The failure at 5% pressure and mixed physical-carbon signs motivate an online, action-conditioned facility marginal carbon estimator combined with an explicit risk-aware decision constraint, developed with independent dates and stronger comparators. No tuning or novelty claims follow solely from this initial pilot.
