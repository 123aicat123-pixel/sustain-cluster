# Independent September/October calendar-transfer milestone

**Date:** 2026-11-05  
**Verified source:** [GitHub Actions 41977156279](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41977156279), source commit `d3d9755a`. Both `calendar-transfer-september` and `calendar-transfer-october` simulator jobs **SUCCESS** and the `policy-contracts` tests also succeeded.  
**Artifacts:** `sci-carbon-calendar-transfer-september` ID `13391989777` and `sci-carbon-calendar-transfer-october` ID `13392531753`; each archive includes JSON and CSV with 24 configuration rows.

## Preregistered comparison and protocol correction

The following methods were FIXED before any completed September/October
policy-comparison outcome was examined:

- `greedy`: queue-aware task-at-a-time carbon/SLA baseline, unchanged FIFO.
- `beam4`: 4-beam, 8-task-chunk joint batch placement with commitment-aware
  FIFO queue forecasts and fixed 30-minute margin.
- `gate50`: same joint batch planner activated only for a batch of at
  least 2 jobs with at least 50% having any *optimistically* predicted
  unbuffered SLA-feasible destination. Else use baseline greedy.
  This threshold was motivated by prior *August* exploratory studies,
  not fitted from the September/October outcomes.

September 1 and October 1 2023 use corresponding 2020 Alibaba-task
calendar slices, with the same fixed seven-day environmental simulation
horizon. Within each calendar month, two later non-overlapping workload
arrival intervals (ticks 288 and 448, 16 ticks each), independently replayed
and drained for 96 ticks. Both seeds 1 and 42, synthetic hardware scales
2% and 10%. These are one shared workload dataset, NOT independent datasets
or unrestricted yearlong production evaluation.

**Strict isolation correction:** The first September CI attempt
[41975832648](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41975832648)
was rightly blocked at the pretest boundary because 14 training tasks
remained undrained at 2% capacity; no policy outcomes were produced by
that failed September trial. Because these three methods use a
predeclared FIXED 30-minute buffer, they do not require local training.
The corrected runner therefore explicitly omits all calibration
admissions but retains the same calendar test windows and frozen
policy parameters; it checks zero pretest training/residual samples.
This is an intentional **separate fixed-policy test**, NOT directly
comparable to the August training-cohort carryover protocol.
The October first-attempt run is not mixed with corrected evidence.

All three arms in each scenario have matched admissions, same-seed clocks,
FIFO execution and exact SAME FINISHED JOB SET (not merely count),
allowing paired measured total facility+network CO2 comparison. Actual
SLA failure includes overdue unfinished work, and the records expose
finished and on-time task counts and gate activations.

## Paired comparison: one row per month/capacity/window, seed-level deltas

A negative `Δ misses` means fewer ACTUAL SLA deadline failures than
greedy. A negative `Δ CO2` means lower measured facility + network
emissions. Two values in each cell are **seed 1 / seed 42**, not
independent sampling replicates.

| Month | Capacity | Future window | Beam4 Δ misses | Beam4 Δ CO2 | Gate50 Δ misses | Gate50 Δ CO2 |
| --- | --- | --- | --- | --- | --- | --- |
| Sep | 2% | 0 | -1 / +4 | +0.74% / -0.80% | +5 / +13 | -0.63% / +2.16% |
| Sep | 2% | 1 | +3 / +15 | +1.40% / +1.63% | +2 / +8 | +1.36% / +2.32% |
| Sep | 10% | 0 | -3 / -1 | -4.29% / -1.60% | -3 / -1 | -4.29% / -1.60% |
| Sep | 10% | 1 | -2 / -6 | -1.56% / -0.42% | -3 / -5 | -0.83% / +0.23% |
| Oct | 2% | 0 | +16 / +13 | +1.03% / -4.91% | +8 / +6 | +1.75% / -4.94% |
| Oct | 2% | 1 | -14 / +6 | +0.55% / +1.43% | -4 / +10 | -0.04% / +2.90% |
| Oct | 10% | 0 | -5 / -2 | -4.26% / -1.62% | -6 / -2 | -3.90% / -1.46% |
| Oct | 10% | 1 | +8 / -7 | -1.63% / +1.87% | +7 / -7 | -1.63% / +1.87% |

## Descriptive across-episode counts (not independent observations)

For each of the following four rows, there are 2 months x 2 windows
x 2 repeated seeds = **8 matched scenario comparisons**:

| Capacity/method | SLA improved | CO2 reduced | Both strictly improved | SLA misses delta (sum) | Mean paired CO2 change |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2% / beam4 | 2/8 | 2/8 | **0/8** | **+42** | **+0.13%** |
| 2% / gate50 | 1/8 | 3/8 | **1/8** | **+48** | **+0.61%** |
| 10% / beam4 | **7/8** | **7/8** | **6/8** | **-18** | **-1.69%** |
| 10% / gate50 | **7/8** | **6/8** | **5/8** | **-20** | **-1.45%** |

The mean CO2 value is the arithmetic mean of 8 seed-specific
*paired percentage changes*, not a pooled emissions ratio. These
episodes are dependent because they reuse the same dataset and
two seeds. Do not report uncertainty intervals as if n=8
independent workload traces.

**Gate activation is NOT safely selective at 2% capacity:** it still
ran joint batch planning in 3--11 of 16 visible workload batches per
scenario and worsened actual SLA in 7/8 scenarios. At 10% capacity
it ran joint planning in 11--16 of 16 batches per scenario, with
5/8 strictly joint CO2+SLA improvements. A fixed 50% current
forecast-feasibility threshold is not enough to identify damaging
congestion regimes under optimistic queue forecasts.

## Main scientific conclusion

**Joint reservation-aware batch scheduling has repeatable *pilot
advantages* in several separate 10%-capacity September/October
calendar slices, but can cause systematic SLA degradation in 2%
severe-congestion settings.** Even at 10%, one October
later-window/seed worsened SLA despite CO2 reduction, and another
improved SLA at higher CO2. The 50% coverage gate helps in a few
cases but does NOT reliably prevent those failures.

This does NOT establish generalized optimality, an SLA probability
bound, statistical significance, real hardware robustness, or
cross-dataset generalization. It is a new temporal workload-slice
check, not an entirely independent new benchmark. The code
still schedules independent tasks, NOT DAG workflows.

## Next research gate

Do not reuse September or October for tuning gate thresholds and
then advertise them as independent evaluations. Fix alternative
state features and candidate methods on a separate training/
validation window, then evaluate on a genuinely untouched month
or a second independent workload dataset. Focus on direct
decision-time **predicted feasible-set scarcity, queue forecast
error, per-DC commitment pressure and task-resource heterogeneity**;
a scalar feasibility fraction alone failed. Require a strict SLA
non-worsening gate and comparable completed-job sets before
carbon improvement claims. An RL method is not justified solely
by these heuristic experiments.
