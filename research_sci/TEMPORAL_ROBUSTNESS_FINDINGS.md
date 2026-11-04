# Temporal robustness milestone, 2026-11-04

Evidence: [GitHub Actions 41812027675](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41812027675); `temporal-robustness` job succeeded on `d36cff52`. Exploratory two-seed stress experiment only, with synthetic capacity set to 2%.

Protocol: choose `fixed_60` using **training + validation only**; compare frozen `fixed_60` to `fixed_30` in two nonoverlapping later clock intervals, starting at ticks 288 and 448. Fixed 7-day simulator duration, matched same-seed training fingerprints and test arrivals. Each test interval is a *separate counterfactual replay*; intervening validation and previous test admissions are omitted. Not a continuous production experiment.

## First later interval (2023-08-04 05:00 UTC)

Each cohort admits 313, finishes 310; three unfinished per seed/treatment.

| Seed | Policy | CO2 kg | Actual deadline failures incl. overdue |
|---|---|---:|---:|
| 1 | fixed_30 | 1591.25 | 197 |
| 1 | fixed_60 | 1572.11 | 206 |
| 42 | fixed_30 | 1678.21 | 201 |
| 42 | fixed_60 | 1750.82 | 200 |

60-minute buffer reduces seed-1 CO2 by 1.20% but adds nine deadline misses; seed-42 deadline misses decrease by one while CO2 increases 4.33%. Mean paired relative CO2 delta +1.56%, mean deadline misses +4. There is **no consistently joint carbon/SLA improvement**.

## Second later interval (2023-08-05 21:00 UTC)

Each cohort admits 448 jobs. **Completed work is unequal**, so absolute CO2 values below must not be interpreted as a valid carbon-efficiency winner.

| Seed | Policy | CO2 kg | Deadline failures incl. overdue | Finished |
|---|---|---:|---:|---:|
| 1 | fixed_30 | 1796.56 | 292 | 439 |
| 1 | fixed_60 | 1826.94 | 280 | 441 |
| 42 | fixed_30 | 1890.53 | 277 | 440 |
| 42 | fixed_60 | 1883.10 | 272 | 441 |

The selected buffer reduces deadline failures by 12 and 5 respectively, while completing two and one additional jobs. The runner has been corrected to emit `null` carbon delta percentages whenever paired completed-work counts differ, preserving raw CO2 for auditing.

**Interpretation:** the validation-selected buffer is not robustly Pareto-improving across the two later windows. These two seeds, shared workload trace and synthetic stress cannot establish statistical significance, formal SLA guarantees, or generalization. Next gate: multiple independent workload periods and workload-pressure regimes, plus explicit SLA/throughput constraints and per-seed comparability checks.
