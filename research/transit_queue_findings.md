# In-transit queue forecast ablation — experimental record

## Failure mechanism identified

`QueueAwareNSGA2Policy` had previously projected the target data
center queue using running tasks, pending tasks, and the current
decision batch, but not jobs already dispatched to that data center
which had not yet completed inter-datacenter transfer. Such jobs are
held by `TaskSchedulingEnv.in_transit_tasks` and enter pending queues
at later simulation steps. Under contention this can produce large,
optimistic predicted-start errors.

The new `QueueAwareWithTransit` variant uses only the **currently
observable** in-transit queue state and orders existing in-transit
arrivals before new actions when timestamps are equal. All genetic
search hyperparameters, action sets, source traces, and simulator
physical accounting remain unchanged. Original `queue_nsga2` remains
an independently selectable baseline; it has not been overwritten.

## Previously verified diagnostic evidence

- GitHub Actions: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41808414587
- Date: Alibaba June 15; seed 733; 5% CPU capacity.
- Original NSGA-II false-safe SLA predictions: 21/291 completed tasks,
  **all 21 on remote routes**.
- Carbon-Guard false-safe: 39, of which 35 remote.
- SLA-Guard false-safe: 38, all 38 remote.
- In the original NSGA-II, 12 false-safe cases had **at least 60 minutes**
  predicted remaining slack. A small generic 15/30-min buffer cannot
  reliably handle those misses.
- A retrospective 60-minute decision buffer reduces original false-safe
  classification to 12, but yields 115 false alarms; **actual execution
  and SLA do not change** in this post-hoc check.

## First controlled 2-seed in-transit mechanism test

Verified Actions run:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41808924277

- 5% CPU capacity; June 15 trace; 16 admission steps, 112 drain steps;
  seeds 501 and 733; matched task cohorts, 291/291 jobs complete per run;
  zero fallback; six unit tests passed, paired task audit passed.
- Same queue-aware NSGA-II optimization budget and underlying simulator.

| Seed | Policy | Start MAE min | False-safe predicted SLA | Real SLA misses | USD cost | kg carbon |
|---|---|---:|---:|---:|---:|---:|
| 501 | Queue-NSGA-II | 30.619 | 52 | 54 | 1125.097 | 3149.023 |
| 501 | With transit | 0.619 | 3 | 15 | 1129.928 | 3175.854 |
| 733 | Queue-NSGA-II | 11.598 | 21 | 24 | 1136.220 | 3070.456 |
| 733 | With transit | 0.052 | 1 | 4 | 1124.148 | 3083.291 |

SLA misses fell 78 to 19, i.e. relative reduction 75.64%, for these
two seeded June task cohorts. Mean facility+transfer carbon **increased**
by ~19.8 kg per run (~0.64%). This is a concrete corrected
scheduling-model improvement, **not** a demonstrated general carbon
or cost Pareto improvement.

## Next gates and scientific limits

- Check August 15 (more arrivals) and October 1 under the same fixed
  settings; the cross-date workflow was submitted but no cross-date
  performance conclusions were available at the time of writing.
- Separate two claims: correcting an omission in *our adapted predictor*
  is not necessarily an original peer-reviewed research contribution.
  The current project schedules independent Alibaba jobs, not DAG workflows.
- Test on dates not used for method development, and show scenario-level
  confidence intervals; two seeds on one date are insufficient.
- Measure planning wall time, capacity overhead and total energy/carbon.
  Correctly modeling in-transit jobs could increase emissions depending
  on its route changes.
- Do not claim that an exact or perfect simulator queue predictor is
  available under future arrivals; the method still ignores yet-unseen
  jobs and approximates discrete step timing.
