# Capacity-pressure x temporal generalization checkpoint

**Date:** 2026-11-04  
**Verified experiment:** [GitHub Actions run 41814556847](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41814556847), all seven jobs SUCCESS, commit `ff64c263`.
**Raw data:** the `sci-carbon-capacity-sensitivity` workflow artifact, ID
`13313984851`; per-seed logs are in the `capacity-sensitivity` job.

## Protocol

A deterministic, validation-only choice is learned ONCE at synthetic
2%-capacity validation: `fixed_60`. That policy is locked before either
later test window is evaluated. The reference is `fixed_30`. For every
setting, two paired seeds (1, 42), **three synthetic DC resource-capacity
scales** (2%, 5%, 10%), and two non-overlapping later windows are evaluated.
Each test window uses separate simulator replay; validation and prior
heldout arrivals are omitted in the replay's gap. This is NOT a continuous
production trajectory nor an independent workload/dataset evaluation.

The same time horizon (7 days), admissions, and within-scenario training
history are enforced. Facility and transmission CO2 are added; actual
completed SLA violations, overdue unfinished jobs and completed-work
identity are checked.

An important improvement over previous studies: equality in the
**number** of completed tasks is not sufficient. We now compute a digest
of the **set of exact finished task names, arrival times, duration and
CPU/GPU/memory demand**, plus completed core/GPU minutes. Carbon deltas
are emitted only when paired completed-task sets match. If they differ,
carbon differences are **null/not directly comparable** instead of being
misrepresented as CO2 savings. Raw totals remain visible.

## Paired time-window results

Here the carbon value is the **mean of two seed-specific percentage
changes**, NOT a ratio of pooled mean CO2 values. SLA deltas are the
mean of absolute changes in observed failed/overdue jobs; negative
means an improvement.

| Scaled DC capacity | Heldout window | Mean CO2 change (fixed60 vs fixed30) | Mean change in deadline failures | Exact completed-work matched in both seeds? |
| --- | --- | ---: | ---: | --- |
| 2% | 0 (tick 288) | +1.56% | +4.0 | Yes |
| 2% | 1 (tick 448) | N/A | -8.5 | **No** |
| 5% | 0 | +1.50% | -2.5 | Yes |
| 5% | 1 | -1.62% | +4.0 | Yes |
| 10% | 0 | -0.03% | -1.0 | Yes |
| 10% | 1 | +0.76% | -9.5 | Yes |

The 2%-capacity later window reports **448 admitted** in every paired
seed, but `fixed_30` finishes 439 and 440 versus `fixed_60` 441
and 441. Reporting a comparative CO2 efficiency value here would be
invalid.

At 10%-capacity, window 0 is near carbon-neutral (mean -0.03%):
seed 1 CO2 falls 0.26% with no change in actual deadline misses;
seed 42 CO2 rises 0.21% while actual misses drop by 2.
That is **not** joint non-worsening on *every* seed. Similarly, every
other window/capacity pair has at least one seed in which CO2 and/or
deadline failures worsen.

## Main conclusion (negative/generalization finding)

**No tested capacity/window combination showed simultaneously
non-worsening CO2 and deadline failures in BOTH paired seeds.** The
60-minute choice made on the prior validation data is not a robust
solution across time and resource pressure. Direction and magnitude
of the carbon/SLA tradeoff vary markedly with resource availability.

The high-capacity absolute CO2 totals **must not** be compared directly
with low-capacity totals to infer algorithmic carbon efficiency:
the synthetic hardware/facility configuration is different. Instead
compare *within the same capacity, test window, seed and exact completed
workload*. There are only 2 seeds, one underlying workload trace,
two future windows and synthetic capacity scaling; no significance
claim, coverage guarantee, or publication-ready generalization is
supported. The benchmark tasks are independent, not DAG workflows.

## Next scientific gate

Before introducing a new adaptive scheduling method, report observed
decision-time queue pressure/utilization and remaining SLA slack by
window. Then test **predeclared** state-conditioned risk budgets
trained/selected only on earlier validation intervals. Compare against
the strongest same-work baselines and certify risk on subsequent,
multiple independently heldout windows; evaluate several seeds and
disjoint workload slices, including the original capacity regime.
A fixed buffer that changes with current utilization is a *baseline*,
not sufficient novelty on its own for an SCI paper.
