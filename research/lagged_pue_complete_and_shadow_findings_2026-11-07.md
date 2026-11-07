# Full prospective Lagged-PUE results and shadow-risk failure analysis — 2026-11-07

**Scope:** Alibaba independent-task placement in simulator; not DAG workflow scheduling or production carbon measurement. All figures are paired, simulator-reported facility + transmission emissions and realized task deadline misses.

## Frozen Lagged-PUE prospective experiment: all 36 policy runs accounted for

Predeclared 3 workload dates × 2 simulated CPU capacities × 2 seeds × 3 policies = **36 runs**, with 12 matched candidate-control comparisons. Original run: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42188960403. Eight candidate-control pairs finished there (24 policy runs); December 10 initialization had failed before admissions. After the precise **December-only** site-index correction, the remaining four pairs (12 policy runs) passed in https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42369032943. They used the original frozen policies/seeds/workload dates; December traces used corrected simulator-local site season indexing, whereas earlier dates retain the upstream approximate mapping. Do not conflate those calendar mapping conventions.

All deltas below are `queue_nsga2_lagged_pue` MINUS `queue_nsga2_indexed_transit`. Negative carbon or SLA is preferable. ALL unfavorable cases are retained:

| Workload | CPU | Seed | Carbon Δ kg | SLA misses Δ | Joint nonworse |
|---|---:|---:|---:|---:|---|
| Jan 20 | 5% | 901 | +56.9952 | +9 | no |
| Jan 20 | 5% | 1701 | -12.2100 | +3 | no |
| Jan 20 | 10% | 901 | -1.2753 | 0 | yes |
| Jan 20 | 10% | 1701 | -24.7359 | -2 | yes |
| Apr 15 | 5% | 901 | +10.8912 | +11 | no |
| Apr 15 | 5% | 1701 | -40.6558 | +12 | no |
| Apr 15 | 10% | 901 | -8.0731 | -17 | yes |
| Apr 15 | 10% | 1701 | -22.7821 | -15 | yes |
| Dec 10 | 5% | 901 | -8.4278 | -3 | yes |
| Dec 10 | 5% | 1701 | +36.9188 | -2 | no |
| Dec 10 | 10% | 901 | -10.9119 | 0 | yes |
| Dec 10 | 10% | 1701 | +5.8281 | 0 | no |

**Total joint nonworse: 6/12 (50%)**, with **5%-capacity 1/6**, **10%-capacity 5/6**. The outcomes reveal strong pressure dependence, but the small number of distinct workload dates (three) and correlated seeds preclude independent-sample inference. A positive performance claim of universal carbon/SLA improvement is not supported.

## Frozen double-NSGA-II shadow taskwise risk guard

Development-only, previously explored dates: Jan 20 and Apr 15, CPU 5%, two seeds each. Successful workflow: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42369702857.

| Date | Seed | Indexed SLA misses | PUE SLA misses | Guarded SLA misses | Guarded-minus-Indexed carbon kg | Indexed planner P95 ms | Guarded planner P95 ms | Whole-batch reversions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Jan 20 | 901 | 10 | 19 | 16 | +34.9597 | 225.41 | 398.52 | 9 |
| Jan 20 | 1701 | 7 | 10 | 9 | -18.6225 | 204.99 | 413.65 | 8 |
| Apr 15 | 901 | 101 | 112 | 110 | +8.9854 | 677.32 | 1374.77 | 11 |
| Apr 15 | 1701 | 101 | 113 | 99 | +7.5674 | 682.60 | 1329.83 | 11 |

The shadow guard reduced realized SLA misses relative to the unguarded PUE policy **in all four development pairs**, yet remained worse than Indexed in three of four. Three of four guarded runs emit more physical-simulator carbon than Indexed; planning P95 increased substantially. Crucially, the guard uses **two complete online NSGA-II searches**, adding 6,400 evaluation requests on top of the 6,400 for each proposal policy. It cannot be described as equal-budget or generally safe.

These results **falsify** a publishable claim that whole-batch reversion automatically guarantees lower SLA or carbon under congestion. Deterministic no-later predicted starts are not a worst-case deadline guarantee under future arrivals and model error.

## Next non-optimistic scientific analysis

Do not tune a new load threshold based on the above outcomes or post-hoc omit adverse rows. New diagnostic `research/route_spillover_audit.py` partitions task-level SLA rescued/harmed into (a) changed destination and (b) unchanged destination. The second partition is suggestive of resource/queue externalities from other tasks but is *not causal identification*. The audit will be run in the already explored Jan/Apr shadow development settings via `.github/workflows/research-lagged-pue-shadow-guard.yml`; it preserves all outcomes and costs, without changing an algorithm.

Publication gate: genuinely action-conditioned incremental facility carbon estimation + an explicit, computationally bounded SLA risk mechanism, with untouched workload-date validation, still require independent development and testing. This experiment establishes neither SCI novelty nor a physical deployment-level energy saving.
