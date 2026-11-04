# SCI pilot: carbon-aware spatial scheduling

This is an **independent experimental branch created from `main`**, not
a derivative of `research-baselines`. All additions live under
`research_sci/` and a dedicated CI workflow. Upstream simulator,
workloads, rewards, and original experiment scripts are left unchanged.

## Research question

Under a common task-level dispatch and network transmission path, does
SLA-feasible carbon-aware spatial placement reduce facility + transfer carbon
emissions without increasing unfinished or overdue tasks?

This stage establishes reproducible **baselines**, not a novel RL algorithm or
publication-quality results.

## Policies

- `round_robin`: deterministic cycling through currently feasible centers.
- `lowest_carbon`: currently feasible center with lowest observed grid carbon intensity.
- `fastest_finish`: currently feasible center with shortest estimated delivery plus execution time.
- `sla_carbon`: among centers meeting *estimated* deadlines, select lowest carbon; otherwise fastest predicted finish.

All policies use the same `can_schedule(task)` filter, the same transmission
delay estimator, the same 15-minute dispatch actions, and a common explicit
fallback to origin (or lowest ID when no origin) if no center is currently feasible.
The fallback may cause downstream queuing and is counted. No temporal deferral
is allowed in this experiment. Never describe the above as reproductions of
upstream native rule-based routing, which has a different transmission pathway.

## Local commands

Install dependencies (prefer isolated Python 3.10 environment):

```bash
python -m pip install -r requirements.txt
unzip -n data/workload/alibaba_2020_dataset/result_df_full_year_2020.zip -d data/workload/alibaba_2020_dataset/
python -m unittest research_sci.test_policies -v
python -m research_sci.run_pilot --steps 8 --drain-steps 24 --seeds 42
```

For exploratory paired multiple-seed checks:

```bash
python -m research_sci.run_pilot --steps 32 --drain-steps 96 --seeds 1 42 2026 --output research_sci/results/pilot_3seeds.json
```

Output JSON and CSV include complete/unfinished/overdue counts and separate
facility and transfer carbon/cost accounting. **The reported ratio
`sla_rate_completed_only` uses completed tasks only** and MUST NOT be
called the final SLA violation rate if tasks remain unfinished.

## Reproducibility gates before paper claims

1. Confirm a clean CI run for unit tests and simulator smoke, including
   lifecycle conservation and matched admission horizons.
2. Validate that the simulation models and units are internally consistent.
   The original reward functions use different cost/emission proxy signals;
   this pilot evaluates from the per-center simulator output instead.
3. Test a longer drain / account for unfinished tasks rather than claiming
   low carbon from leaving work incomplete.
4. Verify matching arrivals, computation, data-center configurations, and
   environment time windows across policies; freeze the commit SHA and seeds.
5. Use disjoint training/validation/test time windows before RL training.
6. Report inference costs, confidence intervals, physical-model assumptions,
   and a sufficiently strong baseline suite.
7. **Do not quote short smoke-test results as SCI evidence.**

## Scientific limitations

- `can_schedule` only checks current capacity. It is not a queue forecast.
- Estimated completion ignores future contention.
- A 15-minute time grid and simulator accounting are modeling assumptions.
- This baseline uses observed carbon intensity; no future prediction or
  uncertainty modeling exists yet.
- The upstream simulation resets some random internal start variables; audit
  the relationship of workload timestamps and environment traces.
- No actual GPU training has been performed at this stage.
