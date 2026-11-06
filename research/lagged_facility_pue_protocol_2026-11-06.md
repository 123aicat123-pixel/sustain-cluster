# Pre-result protocol: lagged facility-PUE carbon-proxy ablation (2026-11-06)

**Research hypothesis (not a result):** using the most recently observed, site-specific IT/HVAC power ratio to scale a task's incremental *proxy* carbon score might change geo-distributed assignment and improve *realized full-simulator* emissions at comparable SLA risk. The opposite (zero intervention, higher carbon or SLA regressions) is equally reportable.

## Scope and rationale

This is independent-task placement with multi-DC queues, not DAG workflow scheduling. Existing predictive work (`facility_lag_forecast.py`) estimates one-step total facility energy from past observations; it is **not action conditional**. The new approach is intentionally a transparent test of whether a *lagged average PUE ratio* is a useful routing heuristic. **Average PUE is NOT marginal PUE** and it ignores battery effects, completion time and HVAC dynamics; do not label it physically calibrated marginal carbon.

For DC j, after observing a completed simulator step s (never at decision time s):
- `pue_j[s] = clip(1 + P_HVAC,j[s] / P_IT,j[s], 1.0, 3.0)` for finite nonnegative measured kW and P_IT > 1e-9.
- Missing/zero IT signal -> multiplier **1.0**, recorded as a fallback. Negative/nonfinite telemetry is an error, not silently imputed.
- Only at the *next* dispatch step s+1, multiply the existing per-task 6 W/core duration × present destination-CI carbon proxy by `pue_j[s]`. Network transfer cost/carbon remain unchanged. This never uses current-step realized energy or future workload, deadlines, cooling, battery or future carbon intensity.
- At the very first dispatch, every site multiplier is 1.0.
- No learned model parameters, train/validation split or post-hoc tuning. PUE clip [1,3] is fixed here before simulation.

## Controlled pair and intended experiments

- **Reference:** `queue_nsga2_indexed_transit` (existing indexed in-transit queue predictor).
- **Candidate:** `queue_nsga2_lagged_pue` (inherits identical indexed projection, NSGA-II population 16, generations 8, candidate sets and objective weights; modifies only facility portion of carbon fitness).
- **Diagnostic heuristic:** `sla_feasible_carbon`, reported separately, not an equal-compute or equal-candidate comparison.
- Exploratory dates: June 15 at CPU 5%; May 19 at CPU 5%; seeds 901 and 1701, 16 admission + 112 drain steps; all previously inspected, **NOT** a blind holdout.
- Keep full task-level cohort identity, lifecycle completion and zero-fallback requirement. Equal optimizer evaluation requests is necessary, but number of distinct chromosomes may change due to optimization path.
- Archive per-run PUE observation/fallback counts, min/max observed ratio, physical facility + transmission carbon, cost, SLA miss counts, planner P50/P95 and search requests. Report all differences **candidate minus indexed reference** without trimming unfavorable cases.
- Do not require identical task outcomes: **a useful carbon proxy must be allowed to change routing**, but immutable task cohorts and matched scenario conditions are mandatory.
- If site PUE never differs from 1, report no intervention and diagnose signal coverage before claiming algorithm validity.

## Interpretive gate

1. Passing simulation/unit CI only validates code and accounting.
2. A decrease in realized physical carbon **with no excessive SLA regression** across several independent dates would justify a new frozen test study; a decrease in *surrogate carbon* alone is insufficient.
3. A lagged PUE predictor is an engineering baseline, not a defensible SCI novelty claim; true action-conditioned marginal facility carbon requires controlled counterfactual methodology or physically calibrated experimental validation.
4. The host's planner compute time/energy is separate from simulated facility emissions; neither should be quietly included in the other.
5. Do not merge to `main` before test/experimental review.
