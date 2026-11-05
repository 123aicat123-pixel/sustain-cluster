# New-month projected-risk batch guards: definitive pilot counterexample

**Date:** 2026-11-05  
**Successful, verified simulation code:** `eacbe9f59981b7a40f2be8c20df2177a1fd95a5c`; GitHub Actions [run 41984149859](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41984149859), **16 of 16 CI jobs SUCCESS**, including **147 independent unit tests**.  
**Raw CSV/JSON evidence:** `sci-carbon-projected-guard-november` artifact ID `13395517611`; `sci-carbon-projected-guard-december` artifact ID `13395577946`. Each has 32 configuration rows (4 methods × 2 capacities × 2 future windows × 2 seeds). Earlier failed December attempt is not a comparable scientific result.

## Fixed interventions — no test-time parameter fitting

- `greedy`: original FIFO queue-aware per-task routing, fixed 30-minute predicted SLA buffer.
- `beam4`: unchanged joint batch 4-beam, 8-task-chunk reservation-aware planning.
- `guard0`: compare beam and shadow greedy from the **same currently visible state**. Adopt beam only if *every task's optimistic completion prediction* is no later than under sequential greedy, plus at least one strict predicted earlier finish or a smaller work-weighted current grid-intensity proxy. Otherwise execute original greedy.
- `guard15`: relax guard0 for jobs whose greedy forecast is at least 30 minutes before deadline: at most **15 minutes forecast delay**, and never consume the original 30-minute reserve. Nonbuffered jobs remain fully guard0-protected.

Both guards are PREDECISION, deterministic, side-effect-free shadow audits (the actual candidate action is only sent to the simulator after acceptance). No future arrivals, realized finish times, forecast residual ground truth or future carbon-intensity values can influence the decision. One-task no-later **forecast** dominance is NOT a rigorous SLA or carbon dominance guarantee.

Workload: Alibaba 2020 task traces aligned to **November 1 and December 1 calendar slices**, simulated with 2023 seasonal time axes, correct 0-based calendar environmental indices and the same fixed trainless 30-minute policy. Every experiment uses seeds 1/42, capacity scales .02/.1, two gapped test arrival windows (ticks 288/448), 16-tick admissions and 96-tick drains. Each replay is complete and paired against the baseline on exactly the same arrivals; all unfinished and overdue jobs are counted. The two seeds share the underlying trace and thus are not independent workload samples.

## Critical simulator boundary repair (not algorithm tuning)

Original `make_env` computes environmental initialization day using an inaccurate `int(month*30.5+day)`. Starting on December 1 incorrectly indexes beyond the 365-day weather array and caused `IndexError: index 35040 is out of bounds for axis 0 with size 35040` on [run 41983542894](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41983542894). The research-only launcher now sets the **exact zero-based 2023 day of year** before `env.reset` for both November and December; bounds checking and unit tests enforce validity. Results from the previous approximate-calendar August/September/October protocols should NOT be pooled as identically initialized environmental timelines with these new months. All new November/December comparisons were rerun with the fixed calendar implementation before the final results below.

## Result by capacity — projected guards versus true greedy

A negative **Δ SLA failures** means fewer *actual* deadline failures (completed late + overdue unfinished). Values are the four same-trace seed/window paired episodes per month/capacity; they are descriptive, not independent statistics.

| New month | Capacity | Beam4 total Δ SLA failures | Guard0 total Δ SLA failures | Guard15 total Δ SLA failures |
|---|---|---:|---:|---:|
| November | 2% | -13 | -14 | **-23** |
| November | 10% | -7 | -8 | **-9** |
| December | 2% | +3 | -8 | **-9** |
| December | 10% | +10 | **+35** | **+34** |

**Notable November result:** Guard15 never increased actual SLA failures in any of its eight individual November scenarios. At 10% capacity, the four matched completed-work sets also had lower measured total facility+network CO2 (mean per-pair relative change **-1.17%**), demonstrating a potential win in that future calendar slice. At 2% capacity, Guard15 mean per-pair CO2 change was **+0.68%**: SLA improved but emissions increased.

**Decisive December counterexample:** at 10% capacity, *later* heldout window:
- Seed 1: Beam4 **+12** actual SLA failures vs greedy; strict Guard0 **+18**; buffered Guard15 **+17**, even though Guard15 accepted only **2/16 batches**.
- Seed 42: Beam4 **+4**, strict Guard0 **+19**, buffered Guard15 **+21**, though Guard15 accepted only **5/16 batches**.
- In all these 10%-capacity paired scenarios, **the exact same task set actually completed**, so these are true SLA differences, NOT throughput/count artifacts. Measured CO2 effects varied: Guard15 had **-0.05% / -0.46%** in those later-window scenarios, a real carbon-versus-SLA tradeoff.

At 2% December, the later-window finished-task identities differ between baseline and several methods, so cross-method per-workload CO2 percentage **must be null and must not be inferred from raw kilograms**. In the earlier window, Guard0 and Guard15 rejected all 16 batch proposals in each seed, reproducing greedy exactly.

## Outcome accounting and guard activation

| Capacity / policy | Nov actual SLA improvement episodes | Nov actual SLA worsening episodes | Dec actual SLA improvement episodes | Dec actual SLA worsening episodes |
|---|---:|---:|---:|---:|
| 2% / Beam4 | 3/4 | 1/4 | 2/4 | 2/4 |
| 2% / Guard0 | 2/4 | 0/4 | 1/4 | 0/4 |
| 2% / Guard15 | **4/4** | 0/4 | 1/4 | 0/4 |
| 10% / Beam4 | 3/4 | 1/4 | 1/4 | 3/4 |
| 10% / Guard0 | 2/4 | 1/4 | 1/4 | **2/4** |
| 10% / Guard15 | 2/4 | 0/4 | 2/4 | **2/4** |

Ties are omitted from the table: for instance December 2% strict Guard0 had one improvement and three ties; the same is true for buffered Guard15. November 10% buffered Guard15 had two improvements and two ties. The guards were **actually active**, not just returning baseline:
- November 2%: Guard15 accepted **16/64** reviewed batches; November 10%: **32/64**.
- December 2%: Guard15 accepted **6/64**; December 10%: **15/64**.

These scenarios demonstrate a **counterexample to the belief that strict per-task predicted no-later protection ensures real deadline non-regression**. The predictor ignores future arrivals and later actions. A batch with one hypothetically improved placement may alter future queue competition, leading to more deadline misses, including tasks that did not even exist when the decision was made.

## Scientific consequence / next experiment (NOT performed here)

**Do not claim any formal SLA protection, safe scheduling, or broadly reliable Pareto improvements from Guard0 or Guard15.** Do not retune either guard's allowance using the already inspected November/December windows and reuse them as independent tests.

To achieve rigorous risk control, future research must move beyond per-task deterministic completion forecasts to **multi-step congestion uncertainty** or a properly validated statistical bound trained on historical *held-out disjoint days*. A more defensible next design:
1. Fit a historical residual/distribution model by observable DC congestion, task resource mix, and committed arrivals, using explicit time-block cross-validation; audit censoring and shift.
2. Model the impact of new assignments on **existing queued jobs and future arrival distributions**, not just the presently assigned batch.
3. Compare a decision-time conservative constraint with full-system realized SLA on a genuinely untouched calendar period and, ideally, a separate trace/dataset, reporting task-identity-matched CO2 and throughput.
4. Test 100% capacity and realistic stress levels, not only 2%/10% synthetic hardware scales.
5. If workflow scheduling is the intended journal topic, add DAG precedence and true workflow completion/deadline semantics. The current simulator schedules independent jobs.

**Status:** reproducible four-arm negative/positive pilot with 16/16 CI jobs passing; not yet a publishable SCI novelty or guarantee.
