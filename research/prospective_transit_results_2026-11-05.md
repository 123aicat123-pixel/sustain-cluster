# Prospective transit queue NSGA-II: complete 36-run outcome (2026-11-05)

**Status:** 6/6 matrix jobs SUCCESS, 36/36 simulator policy runs finished, with full common admitted cohorts, no fallback and no unfinished tasks. These are descriptive simulator results rather than evidence of peer-reviewed novelty or general real-world performance.

**Protocol committed before outcomes:** `research/prospective_transit_protocol_2026-11-05.md` (commit `7e5e9e4c4f60952f3c73442728dea83e53d40175`).  
**Frozen experiment commit:** `2702c440b12c116ee34780ddf277cd61a49290ea`.  
**Verified successful Actions run:** https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41970619250  
**Artifacts:** six `prospective-transit-{feb12,may19,nov12}_{05,10}` artifacts associated with the run, containing task-level and aggregate raw outputs, logs and paired-task audit files.

## Design

- Independent-job multi-data-center spatial placement, not a DAG workflow benchmark.
- Alibaba trace calendar admission starts: **February 12, May 19 and November 12**. Each new calendar date was specified before results. These dates have now been examined and are not an untouched future test partition.
- CPU count scale: 5% and 10% of each configured DC's original CPU count, other resource settings unchanged. Do not compare absolute plant carbon between these differently scaled capacity regimes as though they were one physical system.
- Seeds 901 and 1701 per calendar/capacity combination (same task admission cohort within each calendar/capacity; seed variation is **not an independent workload trace**).
- No-Queue, Queue-NSGA-II, Queue-NSGA-II With-Transit. Population 16, generations 8, compromise weights (0.1,0.1,0.8), common total-capacity action candidates, 16 admission and 112 drain steps.
- 3 dates × 2 capacity scales × 2 seeds × 3 policies = **36 simulator runs**.
- The task-level audit matched cohort keys (seed, arrival_utc, job_name), immutable job attributes, independent SLA counts and completed-task conservation. All 12 paired seed-scenarios eligible; no censored comparisons.

## Full paired results

Carbon and cost columns show With-Transit MINUS Queue-NSGA-II. A positive carbon value means more realized emissions.

| Date | CPU | Seed | Jobs each policy | No-Queue SLA misses | Queue SLA misses | Transit SLA misses | Queue start MAE min | Transit start MAE min | Delta carbon kg | Delta cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Feb 12 | 5% | 901 | 1040 | 39 | 22 | 7 | 0.779 | 0.000 | +0.201 | -3.999 |
| Feb 12 | 5% | 1701 | 1040 | 55 | 56 | 40 | 1.428 | 0.029 | +12.380 | +2.621 |
| Feb 12 | 10% | 901 | 1040 | 1 | 1 | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| Feb 12 | 10% | 1701 | 1040 | 2 | 2 | 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| May 19 | 5% | 901 | 417 | 31 | 30 | 14 | 2.842 | 0.000 | +4.829 | +1.615 |
| May 19 | 5% | 1701 | 417 | 17 | 17 | 9 | 1.871 | 0.000 | +20.580 | +3.496 |
| May 19 | 10% | 901 | 417 | 0 | 0 | 1 | 0.000 | 0.000 | +7.908 | +2.748 |
| May 19 | 10% | 1701 | 417 | 2 | 2 | 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| Nov 12 | 5% | 901 | 373 | 35 | 26 | 13 | 1.930 | 0.241 | +2.470 | +5.621 |
| Nov 12 | 5% | 1701 | 373 | 34 | 26 | 20 | 0.845 | 0.000 | +1.914 | +5.654 |
| Nov 12 | 10% | 901 | 373 | 1 | 1 | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| Nov 12 | 10% | 1701 | 373 | 23 | 23 | 10 | 2.534 | 0.000 | +17.026 | +4.616 |

Rounded to three decimal places; exact per-run values are in archived JSON and task-level CSVs.

## Descriptive within-capacity summaries

| CPU capacity | No-Queue SLA misses | Queue SLA misses | With-Transit SLA misses | Queue → Transit delta | Sum of paired carbon deltas kg | Sum of paired cost deltas USD |
|---|---:|---:|---:|---:|---:|---:|
| 5% | 211 | 177 | 103 | -74 (-41.8%) | +42.374 | +15.008 |
| 10% | 29 | 29 | 17 | -12 (-41.4%) | +24.934 | +7.364 |

Over all 12 paired seed-scenarios there were 206 Queue-NSGA-II SLA misses versus 120 With-Transit misses (-86, descriptive -41.7%). **Do not pool the raw carbon/cost values from the two capacity regimes for physical comparison or statistical inference.** Most improvements at 10% arise from the Nov 12 seed 1701 case; there are numerous zero-effect cases and May 19 seed 901 worsened from zero to one miss.

All With-Transit scenarios had lower or equal recorded dispatch-time start prediction MAE than Queue, and the saved false-safe counts for With-Transit were zero in these conditions. This is not a guarantee of no SLA misses: delayed execution can be correctly anticipated yet still violate a deadline.

## Scientific interpretation and falsification

1. **Supported within this test setup:** in-transit-aware queue accounting improves prediction and reduces overall SLA misses under 5% CPU stress across all three new calendar admission windows and both seeds. The four previous June/August/October positive evaluations should not be counted as independent blind evidence for this held-out result.
2. **Not uniformly beneficial:** under 10% CPU capacity two entire seeds/dates exhibited identical outcomes and one seed/day (May 19, 901) had an extra SLA miss and higher emissions. Strong 'always improves' or 'SLA-safe' claims are falsified.
3. **Carbon remains an unresolved tradeoff:** With-Transit increases realized simulator carbon relative to Queue in every nonzero-carbon-difference scenario in these 12 matched cases. A three-objective Pareto dominance claim is **not supported**. Financial outcomes also vary.
4. **Predictor correctness is not a scheduling improvement guarantee:** zero mean start error can coexist with a missed deadline, since the chosen action might have been suboptimal under the physical objective. Existing current-state observable in-transit modeling corrects an omission in our adapted predictor; it does **not by itself establish a novel scientific algorithm**.
5. **Limitations:** only 3 new admission dates, two correlated seeds/date, 4-hour admission horizons, stress-capacity power-scaling and uncalibrated marginal-carbon fitness, no planner-runtime benchmark, no independently trained strong DRL comparator. No inferential confidence or significance conclusion is asserted.

## Next research gate (to be frozen before new tests)

- Construct an explainable *contention-triggered* switch or prospective risk-constrained intervention using only currently observed queue and in-transit states, with careful separate ablations for actual facility carbon and no queue effects. More complex simulation-based predictor computation may not be necessary when zero backlog.
- Compare with SLA-Carbon, No-Queue, Queue and With-Transit, including prediction quality and planner wall time, under identical legal action candidates and transparent evaluation budgets.
- Calibrate cost/carbon surrogate against measured full simulator facility+transfer effects with previously observed scenarios **only**. Freeze parameters before any new calendar/date testing.
- Reserve additional genuinely unexamined dates and longer admission horizons; use the date (not individual job or RNG seed) as the unit of workload diversity for confidence intervals.

**The measured result is promising for SLA prediction under contention, but does not yet establish SCI publication readiness.**
