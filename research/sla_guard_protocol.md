# Pre-registered SLA-safe carbon-guard test (2026-11-04)

## Motivation

On the previously inspected Alibaba August 15 window (5% CPU capacity),
the unrestricted proxy Carbon-Guard sacrificed many real SLA deadlines
in exchange for a small carbon reduction compared with queue-aware NSGA-II.
A pure proxy-carbon constraint is therefore unsafe under high contention.
On the September 1 window, deadline misses were almost absent.

## Untuned new algorithm

`queue_nsga2_carbon_sla_guard` runs the identical existing queue-aware
NSGA-II genetic search (population 16, generations 8, compromise weights
0.1/0.1/0.8). The only addition is a post-search acceptance rule:

- Compute both optimized candidate and heuristic SLA-Carbon reference
  chromosomes' **present-observable surrogate** carbon and predicted
  total positive deadline tardiness using the existing queue projector.
- If optimized candidate proxy carbon exceeds the reference proxy carbon,
  allow reference fallback **only when** the reference's predicted total
  positive tardiness is not higher than the optimized candidate's.
- Otherwise retain the original optimizer choice. No margin or additional
  tunable penalty is introduced.
- Record the number of carbon fallbacks and number of SLA-risk vetoes.
  This computes two extra surrogate evaluations per nonempty batch,
  outside the unchanged NSGA-II search budget.

This is not a formal real-world SLA or carbon safety guarantee; both
estimates are imperfect. It is an experimentally falsifiable
postprocessing rule, not proof of originality.

## Lock before test

- Workload: Alibaba task trace; simulation year 2023 maps task calendar
  dates to 2020 data by replacing the year.
- Test calendar dates: **June 15** and **October 1**, both not previously
  inspected during prototype tuning.
- Seeds: **501** and **733** for each date, fixed 5% CPU capacity.
- Each run: 16 admission time steps (4h), then 112 drain steps (28h).
- Comparison policies: `sla_feasible_carbon`,
  `queue_nsga2`, `queue_nsga2_carbon_guard`, and
  `queue_nsga2_carbon_sla_guard`.
- All policies use the same task-level environment path, transfer
  treatment, scheduler candidate set and fixed genetic budget where
  applicable. Task-level cohort keys, lifecycle and arithmetic are
  independently checked.
- If any policy fails to drain the entire common cohort or uses fallback,
  report that scenario as censored, not a full-cohort ranking.
- Report all three physical objectives (facility+network cost, carbon,
  SLA misses), and raw paired task completions and intervention counts.
- Do not adjust the rule based on these dates; this is an initial
  out-of-date falsification attempt, not statistical proof.

## Prior art and next gate

See `research/novelty_prior_art.md`: carbon, queue, deadline and
adaptive scheduling already have extensive 2026 prior art.
If this policy performs well, subsequent work must calibrate incremental
facility-carbon predictions on truly separated dates and compare to
strong literature baselines before a paper novelty claim.
