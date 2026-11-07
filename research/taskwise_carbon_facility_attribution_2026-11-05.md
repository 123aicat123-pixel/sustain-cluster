# Taskwise carbon selection vs aggregate-risk selection: complete negative-result audit

**Date:** 2026-11-05  
**Scope:** multi-data-center independent task placement; not DAG workflow scheduling.  
**Evidence:** successful, fully archived GitHub Actions simulation run: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41982332747  
**Raw matched runs:** 3 explored date/resource scenarios × 2 seeds × 3 policies = **18 simulator runs**; all fully drained with zero fallback. Same in-admission tasks and 6,400 optimizer evaluation *requests* per policy/seed. Earlier exploratory data already influenced policy design, so none of these constitute new untouched confirmation.

The three policies:
- **With-Transit**: standard NSGA-II knee solution using observable in-transit queue prediction.
- **Aggregate-risk Pareto choice**: cheapest *surrogate*-carbon candidate on the final front, subject to no greater predicted missed-deadline COUNT or total predicted tardiness.
- **Taskwise Pareto choice**: cheaper surrogate-carbon candidate only if **no individual task's predicted completion is later** than in the standard knee solution. This restricts the old aggregate-risk policy and does not use future trace labels.

## Complete results

Columns show **candidate minus With-Transit**. Positive emissions represent more actual simulator-reported emissions; SLA is missed-deadline count.

| Date | CPU | Seed | Baseline SLA | Aggregate-risk SLA | Taskwise SLA | Aggregate carbon Δ kg | Taskwise carbon Δ kg | Taskwise front swaps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| June 15 | 5% | 901 | 6 | 16 | 6 | -65.353 | 0.000 | 0 |
| June 15 | 5% | 1701 | 24 | 18 | 19 | +27.759 | +2.706 | 2 |
| November 12 | 5% | 901 | 13 | 26 | 13 | -5.399 | 0.000 | 0 |
| November 12 | 5% | 1701 | 20 | 21 | 20 | -5.542 | 0.000 | 0 |
| May 19 | 10% | 901 | 1 | 1 | 1 | -3.764 | -0.203 | 1 |
| May 19 | 10% | 1701 | 2 | 1 | 2 | -31.823 | 0.000 | 0 |

Taskwise policy did not increase SLA-miss counts in these **six explored seed-scenarios**, although on June 15/1701 it reduced them from 24 to 19 at +2.706 kg carbon. It was identical to the baseline in four of six scenarios and changed only one decision batch in May 19/901, yielding -0.203 kg carbon and unchanged SLA. It is **too restrictive to demonstrate a meaningful, robust carbon improvement**; no SLA safety theorem follows because future arrivals are unknown.

## Physical-carbon decomposition (simulator reported, taskwise candidate minus baseline)

| Date | CPU | Seed | Facility carbon Δ kg | Transfer carbon Δ kg | Facility energy Δ kWh | Total carbon Δ kg |
|---|---:|---:|---:|---:|---:|---:|
| June 15 | 5% | 901 | 0.000 | 0.000 | 0.000 | 0.000 |
| June 15 | 5% | 1701 | +2.550 | +0.157 | -9.063 | +2.706 |
| November 12 | 5% | 901 | 0.000 | 0.000 | 0.000 | 0.000 |
| November 12 | 5% | 1701 | 0.000 | 0.000 | 0.000 | 0.000 |
| May 19 | 10% | 901 | -0.203 | 0.000 | -0.157 | -0.203 |
| May 19 | 10% | 1701 | 0.000 | 0.000 | 0.000 | 0.000 |

**Important anomaly:** June 15/1701 shows **lower measured facility energy** yet **higher facility carbon**. This is arithmetically possible because electricity carbon intensity and the scheduling of energy consumption across centers/times differ; it does not by itself identify which factor caused the observed difference. Likewise, facility and transfer components need to be analyzed separately, not collapsed into an incremental 6 W/core proxy.

For aggregate-risk, e.g. November 12/901: total carbon decreased 5.399 kg = facility -7.386 kg + transfer +1.987 kg, but missed deadlines doubled (13→26). Thus neither surrogate-carbon minimization nor aggregate SLA prediction guarantees the desired real outcome.

**Scientific decision:** retain With-Transit as the most reliable current SLA baseline, treat both Pareto postselectors as exploratory ablations, and stop implying that a more restrictive predicted-risk cap solves carbon optimization. The next gate is a **past-observable per-datacenter / per-time-step facility energy and CI telemetry audit** (including cooling, battery and transfer accounting), a model fitted on training dates only, and a frozen test on genuinely unexamined dates. New model predictions must be compared to measured carbon without using realized outcomes at decision time; preserve action candidates and evaluation request budgets.

Raw evidence is stored as three Actions artifacts in run 41982332747: `taskwise-carbon-jun15_05`, `taskwise-carbon-nov12_05`, `taskwise-carbon-may19_10`. The reported numbers were independently recomputed from the raw JSON in these ZIPs, including facility and transmission splits; simulator arithmetic identities are checked by the existing `research/physical_accounting.py` module.

**No claim of SCI readiness, statistically independent results, real-world physical calibration, or guaranteed SLA safety is justified by this dataset.**
