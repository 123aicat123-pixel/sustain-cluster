# Lagged-PUE pilot: complete mixed outcomes and frozen next-date test

Date: 2026-11-06. **Scope:** independent-job placement in SustainCluster. This is NOT DAG workflow scheduling or measured physical deployment carbon.

## Completed development-stage experiment

Frozen pre-result protocol: `research/lagged_facility_pue_protocol_2026-11-06.md`.
Frozen policy and successful workflow: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42166905946
Commit under test: `beb30c0d8b6b5408a5c952cc3b1899b4e7b2cc11`.
Two successful matrix jobs, with three compared policies × two seeds × two dates = 12 completed fully drained runs; shared task cohorts and optimizer-request budgets passed audit. Each seed shares a calendar admission trace, **not an independent workload date**.

**All differences below are lagged-PUE minus indexed-transit.** Negative carbon means reduced simulator-reported *facility plus transmission* emissions; negative SLA means fewer misses. No row is suppressed for being unfavorable.

| Date | CPU scale | Seed | Jobs each | Changed destinations | Carbon Δ kg | SLA misses Δ | Cost Δ USD | Planner P95 Δ ms | Task-level SLA rescued / harmed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| June 15 | 5% | 901 | 291 | 83 | -7.810934 | -4 | -0.700055 | +12.835 | 5 / 1 |
| June 15 | 5% | 1701 | 291 | 98 | -10.307627 | -2 | -0.977433 | -9.047 | 13 / 11 |
| May 19 | 5% | 901 | 417 | 97 | +1.087074 | -2 | -0.812957 | -0.442 | 7 / 5 |
| May 19 | 5% | 1701 | 417 | 81 | -12.840284 | +5 | -2.641063 | +3.914 | 5 / 10 |

All candidate runs recorded 640 nonunit lagged-PUE site observations, zero missing observations, and a maximum site ratio between 2.188 and the predeclared clip of 3.0. This demonstrates that the historical facility signal was present, **not** that it was a valid marginal-carbon model.

## Exact scientific interpretation

1. The pilot rejects the claim that Lagged-PUE **uniformly improves both** realized carbon and SLA: one seed/date worsened carbon, another worsened SLA. June 15 is positive exploratory evidence but was used during development.
2. Proxy improvement is not a physical-carbon guarantee. Past-site average PUE may rank placements differently from the true action-conditioned incremental facility cost; HVAC, future load/CI and battery energy are not modeled causally.
3. More route changes do not imply better physical optimization. The candidate altered 81–98 task destinations in each scenario but benefits were heterogeneous.
4. Timing differences mix signs and are collected on shared hosted CPUs; no universal algorithm acceleration is supported.
5. The no-extra-tuning constraint protects the next study from seed/date cherry-picking. The above date/seed results will NOT determine a fitted PUE clip, SLA threshold or new model coefficient.

## Locked next-date experiment **before outcomes**

Use the **unchanged** `queue_nsga2_lagged_pue` and `queue_nsga2_indexed_transit` policies (plus descriptive `sla_feasible_carbon`) on three additional 2020 Alibaba admission dates, chosen here before their outcomes are inspected:
- January 20 (`01-20`)
- April 15 (`04-15`)
- December 10 (`12-10`)

At each: simulated CPU capacity factors 0.05 and 0.10, seeds 901 and 1701, 16 fresh admission steps followed by 112 drain steps, common action and transmission semantics. This design requests **3 dates × 2 stress scales × 2 seeds × 3 policies = 36 policy simulations**. These are new to this targeted Lagged-PUE scheduling experiment; no assertion about worldwide or repository-wide novelty of these dates is possible.

**Primary descriptive evaluation:** for every date × CPU factor, report each seed's *joint condition* (candidate carbon Δ <= 0 kg AND candidate SLA misses Δ <= 0), absolute kg and SLA miss differences. No post-hoc exception for small positive emissions or a nonzero increase in misses. The percentage of joint-nonworse scenario/seed pairs is descriptive only.

**Secondary:** compare real simulator total cost, P95 planning wall time, changed task destinations, rescued/harmed SLA labels, PUE telemetry availability/clip, and the cheap SLA-Carbon heuristic under matched task cohorts. Search requests must match between the two NSGA-II treatments, not the heuristic.

**Eligibility:** zero fallback, all admitted tasks finished, matched exact task identities + deadlines/resource characteristics, reconciled lifecycle and carbon totals, finite metrics. If a scenario has zero tasks or cannot fully drain, retain the failure/censoring and do not silently replace the date.

**Decision rule:** even if many new trials satisfy the joint condition, do NOT claim SCI novelty or statistically significant superiority on correlated random seeds. After this audit, decide whether a genuine prospective action-conditioned marginal facility-carbon model plus separate development/test dates is required. Never retune based on January/April/December outcomes and describe those dates as untouched again.

Existing source of the above development results: `lagged-facility-pue-{june15_05,may19_05}` artifacts in run 42166905946.
