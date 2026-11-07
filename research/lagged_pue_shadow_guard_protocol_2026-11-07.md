# Pre-result development test: past-PUE with shadow taskwise start guard

**2026-11-07**. This study is a proposed *risk guard*, not calibrated marginal emissions, real-world SLA safety, or a demonstrated scientific innovation.

## Problem indicated by the frozen PUE pilot

On the first two additional successful calendar days (Jan 20 and Apr 15), all four 5%-capacity seed pairs had MORE realized SLA misses than the unchanged indexed baseline, whereas at 10% all four were carbon-and-SLA nonworse. The predeclared December tests initially failed in the upstream site trace initialization, and are separately being recovered without replacing their dates.

## Proposed, explicit double-search guard

A `QueueAwareLaggedPUEShadowGuard` runs two separately seeded online NSGA-II searches per nonempty batch: (A) existing PUE-adjusted carbon scorer, (B) **PUE-blind indexed-transit reference**. They use identical observed current state, in-transit queues, task set and GA configuration, without future workload. The PUE proposal is accepted only if **each** task's independently predicted start timestamp is no later than the shadow baseline's predicted start. Otherwise the *whole batch* reverts to the reference actions.

- This guard tests whether taskwise no-later completion estimates reduce the realized SLA degradation.
- It cannot enforce a true SLA constraint: future arrivals and queue prediction errors remain.
- Two optimizations are not equally expensive to a one-search baseline; report `nsga2_evaluation_requests`, `shadow_evaluation_requests`, `total_nsga2_evaluation_requests`, wall-clock P95 and guard interventions. Never claim equal compute budget with baseline.
- The guard changes proposal selection without modifying search weights, in-transit forecast, PUE clip or simulator physical accounting. Report every actual carbon/SLA outcome even if worse.
- Original lagged-PUE reference and indexed-transit control remain frozen.

## Controlled exploratory run

Use Jan 20 and Apr 15, at CPU 5% only (both already examined). Seeds 901 and 1701; three policies each (indexed, plain PUE, shadow guarded PUE) = 12 simulator policy runs, 16 admission steps and 112 drain, same task cohorts. The samples are **not new independent holdout dates**. The exploratory workflow is `.github/workflows/research-lagged-pue-shadow-guard.yml`.

Primary descriptive questions for every paired seed:
1. Does the guard revert any proposals at all, and are the per-task forecasts conservative relative to the shadow?
2. Does realized SLA violation regress less than unguarded Lagged-PUE? If SLA does not improve, this guard does not solve the failure mode.
3. Does the guard give back the PUE carbon improvement, or cause worse realized carbon?
4. How much scheduler compute does doubling the GA budget consume?

Eligibility: equal admission identities, 100% completion, zero fallback, lifecycle audit, equal *per-search* budget; no claim that total budgets match. The 12 simulator runs are development diagnostics only.

A result showing fewer misses but no carbon gains (or twice the compute time) may motivate a cheaper single-search risk-aware method later; it is not sufficient for a paper-ready novelty claim.
