# Queue scheduling / routing forecast factorial — verified milestone

**Date:** 2026-11-05  
**Verified CI:** [GitHub Actions run 41971931470](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41971931470), commit `dea4302d`; **all 11 CI jobs succeeded**, including the new `queue-factorial-ablation` and original baseline tests. `policy-contracts` passed **110 tests**.  
**Raw evidence:** `sci-carbon-queue-factorial` workflow artifact **13390007336**, with 32 per-configuration rows, including exact completed-work digest checks. The earlier matched FIFO vs EDF initial experiment is [run 41971254491](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41971254491).

## Question and controlled intervention

Does the deterioration of SLA under EDF arise from **actual pending
queue order** or from **altered routing placements induced by queue
forecasts**? The baseline always uses FIFO during chronological training.
At held-out test start, four variants are predefined and fully
re-simulated under identical same-seed arrivals:

| Real datacenter pending-queue execution | Router queue-completion forecast | Treatment |
| --- | --- | --- |
| FIFO | FIFO | original baseline |
| EDF | FIFO | execution-order intervention with intentionally mismatched forecast |
| FIFO | EDF | routing-forecast intervention with intentionally mismatched execution |
| EDF | EDF | matching joint EDF deployment |

The actual datacenter pending queue is sorted only immediately before
its ordinary `dc.step`, AFTER current in-transit arrivals have been
delivered. The forecast mirrors the specified queue order and uses
the same prior commitments. The training cohort is unchanged.
No future arrivals or actual outcome labels enter predictions.

This is a **2x2 dynamic-policy factorial**; routing decisions may
react to past results of queue execution, so interactions exist.
Differences are descriptive effects of separate full policy replays,
NOT independent causal contributions estimated from static outcomes.

## 10% synthetic capacity: same completed task sets in all 16 runs

Each future window includes 313 or 448 admitted tasks per seed.
Both seeds share the underlying workload trace. All variants complete
exactly the same actual test-task set within each seed/window.

| Window | Seed | FIFO/FIFO SLA misses | EDF/FIFO | FIFO/EDF | EDF/EDF |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 68 | 69 | 123 | 128 |
| 0 | 42 | 72 | 72 | 126 | 103 |
| 1 | 1 | 140 | 132 | 177 | 173 |
| 1 | 42 | 145 | 140 | 195 | 209 |
| **Four-run sum** | | **425** | **413** | **621** | **613** |

- Changing only actual queue execution to EDF while keeping the
  FIFO prediction gives **12 fewer SLA misses in aggregate**
  (69 vs 68 is worse in one seed/window; two other episodes improve,
  one unchanged). This is **not consistently beneficial**.
- Changing only routing's forecast to EDF while keeping actual
  FIFO execution produces **196 additional SLA misses**.
- Changing both to EDF produces **188 additional SLA misses**.
- Real carbon changes are much smaller and mixed; carbon reductions
  of ~0.1–1.9% in some episodes do NOT compensate for 31–64
  additional SLA misses under matched EDF/EDF.
- The policy's selected route signature differs from baseline in
  all three nonbaseline variants: re-routing occurs, even if actual
  queue execution order is the only explicit initial intervention.

## 2% synthetic capacity: stronger interactions, different finished sets

| Window | Seed | FIFO/FIFO SLA misses | EDF/FIFO | FIFO/EDF | EDF/EDF |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 197 | 202 | 211 | **194** |
| 0 | 42 | 201 | 202 | 209 | **200** |
| 1 | 1 | 292 | 296 | 321 | 327 |
| 1 | 42 | 277 | 284 | 326 | 319 |
| **Four-run sum** | | **967** | **984** | **1067** | **1040** |

- Matched EDF/EDF can help in the first future window but increases
  deadline failures substantially in the later busier window.
- Some variants finish *different task sets* at 2% capacity. The
  runner reports `null` comparative carbon deltas when exact
  completed work differs, and reports raw emissions, CPU-minutes
  and censored/overdue unfinished tasks separately.
- Different queue and routing interventions interact, and the
  direction of interaction changes by window/seed.

## Main research conclusion

**Simple EDF is not a reliably SLA-improving extension of
queue-aware carbon routing in these tests.** More importantly, the
large SLA penalty at 10% capacity arises primarily when the routing
forecast is changed to EDF, which changes subsequent placements.
This finding motivates *joint multi-job, multi-data-center*
congestion/commitment coordination, rather than local per-center
EDF alone. It does NOT establish that FIFO forecasting is
intrinsically more accurate in every setting or that EDF execution
cannot help when coupled to a better planner.

The original queue-aware policy is locally greedy: choose the
lowest-current-carbon-intensity center among predicted buffered-safe
choices, or predicted fastest if none is safe. It does not jointly
optimize a batch, compensate for later batch arrivals, or budget
cumulative SLA damage from prior same-batch assignments.

## Publication limitations and next research gate

- Four same-trace seed/window cells per capacity are NOT independent
  repeated seasons; capacity is synthetic (2%/10% of reported DCs).
- Actual job completion / deadline outcomes are measured, but queue
  predictions are optimistic, no future arrivals are modeled, and
  carbon grid intensity is only a routing proxy, not marginal job CO2.
- These are **independent jobs**, not DAG workflow precedence constraints.
- EDF is a well-known heuristic, not SCI methodological novelty.
- A suitable next baseline is **joint batch assignment with explicit
  commitment-aware congestion / deadline budgets**, compared in the
  same simulator, using held-out time windows never used for tuning.
- Carefully test queue estimator fidelity and separate actual facility
  plus transmission emissions from current carbon-intensity scoring.
- Require same task admissions, reported true on-time rate,
  completed task identity, unfinished overdue jobs and carbon
  comparability for each paired evaluation.

**Decision:** do NOT claim EDF is an improvement; do NOT progress
directly to RL before a principled joint feasible-set baseline is
implemented and tested.
