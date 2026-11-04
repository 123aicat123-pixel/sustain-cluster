# SCI carbon pilot: empirical checkpoint (2026-11-04)

**Status:** All smoke, unit, paired-seed and synthetic stress jobs completed
successfully for commit `69d9394`.

**GitHub Actions evidence:** [CI run 41789905645](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41789905645).
Raw run JSON/CSV and per-policy summaries are attached as workflow artifacts.
These results are *exploratory*, not SCI-ready findings.

## 32 admission steps + 96 drain steps, three paired seeds

Every policy finished 776 tasks per seed, with no end-of-horizon leftovers.

| Policy | Mean reported carbon (kg) | Mean paired carbon change vs round robin |
| --- | ---: | ---: |
| round_robin | 57,634.34 | 0.00% |
| lowest_carbon | 57,104.84 | -0.92% |
| fastest_finish | 57,122.21 | -0.89% |
| sla_carbon | 57,100.73 | -0.93% |
| slack_wait_once | 57,118.34 | -0.90% |
| causal_carbon_wait | 57,148.26 | -0.84% |
| queue_risk_carbon | 57,070.70 | -0.98% |
| queue_risk_defer | 57,128.54 | -0.87% |

The marginal improvement of queue_risk_carbon over lowest_carbon is about
**0.06%** using these means. This tiny effect with three seeds does not
establish superiority or statistical significance. It could be smaller than
the variability attributable to workloads, simulated facilities and time windows.

## 16 admission steps + 64 drain steps, capacity scaled to 2%

This is a deliberately synthetic heavy-contention stress scenario. Every
method admitted **417 tasks per seed**, but many tasks remained unfinished
and overdue at the evaluation horizon.

| Policy | Mean reported carbon (kg) | Mean tasks finished | Mean unfinished overdue |
| --- | ---: | ---: | ---: |
| lowest_carbon | 1,482.58 | 335.0 | 82.0 |
| sla_carbon | 1,560.64 | 334.5 | 82.5 |
| queue_risk_carbon | 1,426.19 | 329.0 | 88.0 |
| queue_risk_defer | 1,436.60 | 319.5 | 97.5 |

**Critical interpretation:** queue_risk_carbon's approximately 3.72% lower
reported carbon vs lowest_carbon accompanies **6 fewer completed tasks**
and **6 more overdue unfinished tasks** on average. The deferred variant
completes **15.5 fewer tasks** and has **15.5 more overdue tasks**. These
are NOT valid carbon-efficiency wins, because the amount of completed work
differs. All existing results are from just two stress seeds, and they do
not support formal causal or significant superiority claims.

**Positive validation:** queues meaningfully affect choices in this stress
scenario. The runner reports 702 and 792 queue-estimate actions for
queue_risk_carbon across the two seeds; the lightweight three-seed default
has zero such events. This supports testing queue-aware placement under
resource contention rather than assuming it adds value in idle systems.

## What this experiment invalidates

1. It is not defensible to optimize only horizon CO2 while ignoring work
   completed or deadline violations.
2. Current FIFO queue prediction is optimistic: it ignores future arrivals
   and other tasks committed in the same decision batch. A fixed
   30-minute risk buffer is NOT an uncertainty-calibrated SLA bound.
3. The default workload is too uncongested to make serious claims about
   queue-risk-aware scheduling. Synthetic capacity scaling changes the
   benchmark and must not be presented as its default workload.

## Next scientific gates

- Log **decision-time finish predictions versus actual finish timestamps**
  to measure forecast bias, MAE, upper-tail error and calibration.
- Incorporate already-in-transit work and same-batch dispatch reservations
  into queue prediction to reduce optimistic waiting estimates.
- Use an SLA-constrained evaluation (compare equal completed work, overdue
  tasks and admission load), not just lower total CO2.
- Test broader arrival rates/capacity combinations, held-out temporal slices,
  5+ paired seeds, and independent workload characteristics.
- Only after reliable risk measurement should a chance-constrained RL or
  learning-to-rank algorithm be attempted.

**Scope protection:** The upstream data-center simulator, original code,
`main`, and `research-baselines` have not been changed by this checkpoint.
