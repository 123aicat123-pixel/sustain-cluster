# Research decision memo: queue-aware carbon-guard scheduling

**Status:** exploratory research decision, 2026-11-04. No manuscript
superiority claim is authorized by this memo. The work is for independent
jobs in multi-data-center placement, NOT DAG workflow dependency scheduling.

## Evidence hierarchy

### 1. Queue-awareness alone is not consistently beneficial

At 5% of original CPU capacity, identical task-admission cohorts,
seed 42: full Queue-NSGA-II had 126 SLA misses vs No-Queue's 167, but
higher carbon 4592.977 vs 4260.029 kg.

Three additional seeds (27182, 12345, 8080) yielded Queue vs No-Queue
SLA misses of 111 vs 157, 144 vs 135, 128 vs 125. Queue benefited
one seed and worsened two; realized carbon increased in all three.
Verified run: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41794110427

Thus a strong, general statement about improving SLA is **not supported**.

### 2. Carbon mismatch attribution

The single-seed 5%-capacity observed queue carbon penalty against No-Queue
was +332.949 kg, decomposed into +329.983 kg facility (99.1%) and
+2.965 kg network transmission emissions. Facility costs were
USD 14.259 lower; transmission costs USD 17.542 higher.
Verified run: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41794740577

This is a mathematical decomposition of simulated outcomes, not a
real-world causal calibration or a validated marginal-energy predictor.

### 3. Strict proxy-carbon guard — a promising falsifiable prototype

The Guard variant performs exactly the same online NSGA-II search as
Queue-NSGA-II, then compares its estimated incremental carbon to the
reference SLA-Carbon chromosome and may replace the optimized choice.
It does not use future physical energy or future workload values.
A carbon proxy bound is **not** an actual plant-emissions bound.

Under 5% CPU capacity, seed 42 / 12345 / 8080, 16 admission steps
plus 112 drain steps, the four candidate policies each finished all
417 tasks with zero fallbacks and independent SLA checks.

| Seed | Full cost USD | Guard cost USD | Full carbon kg | Guard carbon kg | Full SLA misses | Guard SLA misses | Guard interventions |
|---|---:|---:|---:|---:|---:|---:|---:|
| 42 | 1233.314 | 1262.702 | 4592.977 | 4344.713 | 126 | 127 | 3 / 16 |
| 12345 | 1238.115 | 1225.982 | 3835.459 | 3583.949 | 144 | 114 | 4 / 16 |
| 8080 | 1216.367 | 1220.792 | 3848.535 | 3709.481 | 128 | 124 | 5 / 16 |

Across these three seeds, mean cost increased about USD 7.227 versus
original Queue-NSGA-II; mean realized carbon decreased about 212.943 kg
(5.20%); total SLA misses fell from 398 to 365. These seeds were
already used in algorithm exploration, so they are **not an independent
blind test**. Three replicates are not enough for a significance claim.

For reference, the SLA-Carbon heuristic's same-seed costs were
USD 1275.087 / 1243.628 / 1231.467, carbon emissions
4355.207 / 3610.513 / 3713.547 kg, and SLA misses 140 / 127 / 132.
Guard is numerically lower on all three metrics per seed in **this
particular experimental setup**. Do not extrapolate this to unseen
arrival dates, capacity regimes or more challenging workloads.

Verified run:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41795204518

Raw artifact:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41795204518/artifacts/13304843817

### 4. Critical limitation in what varies with seed

`simulation.cluster_manager.DatacenterClusterManager.reset` randomizes
data-center initial day/hour around the configured initialization
day, but `get_tasks_for_timestep` retrieves Alibaba jobs using the
environment's `current_time` with year replaced by 2020. Hence
different RNG seeds do **not** automatically mean different Alibaba
task calendar days. Prior multi-seed results vary environment/random
origins but generally share the same task arrival window.

The research runner now accepts explicit `--start-month` and
`--start-day`, and has an independent two-calendar-date comparison
workflow at:
https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41796118426

**This cross-date workflow has not yet been recorded as successful
by this memo**; inspect its run outcome and raw cohorts first.

## Scientific cautions and next gates

1. Confirm the two dates actually result in DIFFERENT task cohorts
   and full completion with no fallback; if either fails, flag the
   scenario censored. Do not compare truncated emissions or SLA counts.
2. Measure paired algorithm differences on **independent workload dates**
   and resource stress levels, holding optimization budget and
   candidate set constant. Reserve an untouched date/test partition.
3. Quantify queue start-time prediction errors, not just full-episode
   aggregate SLA differences.
4. Develop a calibration method for **actual facility marginal carbon**
   based strictly on past-observable telemetry; distinguish base
   plant consumption, cooling, battery and IT workload effects.
5. Check a potential temporal alignment issue: in
   `envs/sustaindc/sustaindc_env.py`, `SustainDC.step` computes
   `_perform_actions` before it schedules current pending jobs and
   updates DC workloads. This can induce a one-step latency between
   task placement and reported electricity effects. Verify and
   independently test before claiming a physics or decoder bug.
6. Report scheduler decision runtime, CPU overhead, proxy evaluations
   and scenario-level confidence intervals in addition to cost,
   carbon and deadline misses.
7. Novelty is not established: see `research/novelty_prior_art.md`.
   Several peer-reviewed 2026 papers already combine cost/carbon/SLA,
   queue awareness and online carbon-aware scheduling. A genuine
   methodological contribution needs differentiated physical
   calibration/robustness and stronger independent baselines.
8. Do not merge the draft research branch to default `main` until
   the platform and experimental design are independently reviewed.

**Decision:** retain Carbon-Guard as a candidate; reject strong
claims about Queue-NSGA-II alone. Next evidence hinge is independent
calendar-date and stress-condition validation, not more tuning
on August 1 or previously explored seeds.
