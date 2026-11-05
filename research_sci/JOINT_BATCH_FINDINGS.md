# Joint batch commitment beam: mixed but promising matched-simulator results

**Date:** 2026-11-05  
**Code run:** [GitHub Actions 41973766614](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41973766614), at commit `80330169`. The new `joint-batch-ablation` job finished **SUCCESS**; `policy-contracts` passed **119 unit tests**.  
**Artifact:** `sci-carbon-joint-batch` (ID `13390404028`), including 8 paired scenario results as JSON/CSV. This is a pilot observation, not a statistically validated SCI claim.

## Algorithm and fairness conditions

- The original **FIFO** execution and routing queue forecast are retained.
- Training/history are identical for both policies; at heldout test start,
  the policy switches from per-task `QueueRiskCarbonPolicy` greedy to
  deterministic, bounded, 4-state beam search over eight-task chunks
  of each *currently visible* batch. Same action list/transport path.
- Candidate branches each retain their own in-transit and earlier-batch
  pending task reservations; no actual future arrivals, finishes or
  future carbon traces are observed.
- The predeclared ranking is lexicographic: fewest **optimistically
  forecast** deadline misses, summed lateness, buffered infeasibility
  count, then work-weighted **instantaneous carbon intensity proxy**.
  The carbon proxy is NOT actual incremental energy emissions.
- CPU/GPU/memory capacity, 15-minute queue grid, 7-day simulator
  duration, seeds, admission fingerprints, calibration history,
  true SLA outcomes and all unfinished/censored jobs are matched/audited.
- **Carbon percentage deltas are only computed if exact finished job
  identity sets match**. Differing completed work sets receive a
  `null` percentage, regardless of raw absolute emissions.

## Eight real-simulator paired heldout results

A negative SLA delta means the joint batch method has *fewer* actual
deadline failures (including overdue unfinished jobs). Carbon delta
is relative to greedy on the exact identical completed job set;
positive means higher emissions.

| Synthetic capacity | Future window | Seed | Greedy SLA failures | Joint SLA failures | SLA delta | Finished greedy/joint | CO2 change if identical work |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| 2% | 0 | 1 | 197 | 205 | **+8** | 310 / 310 | **+0.13%** |
| 2% | 0 | 42 | 201 | 207 | **+6** | 310 / 310 | **+1.22%** |
| 2% | 1 | 1 | 292 | 290 | **-2** | 439 / 440 | **N/A** |
| 2% | 1 | 42 | 277 | 279 | **+2** | 440 / 440 | **-1.76%** |
| 10% | 0 | 1 | 68 | 70 | **+2** | 313 / 313 | **-2.02%** |
| 10% | 0 | 42 | 72 | 68 | **-4** | 313 / 313 | **-1.08%** |
| 10% | 1 | 1 | 140 | **130** | **-10** | 448 / 448 | **-1.31%** |
| 10% | 1 | 42 | 145 | **134** | **-11** | 448 / 448 | **-2.03%** |

Every paired intervention changed the route signature, showing that
the planner was active rather than silently reproducing greedy actions.
The 2%-capacity episodes selected 15 or 16 visible batches and
roughly 5,555 or 8,015 candidate expansions per episode; the 10%
episodes used identical workload/expansion counts.

### Notable success — 10% capacity, later time window

Both seeds have *identical finished task sets*, not just identical
counts. The joint batch method reduces SLA failures by 10 / 11 tasks
while decreasing measured facility+network CO2 by 1.31% / 2.03%.
This is **an interesting paired pilot finding**, not an independent
validation result: this heldout window has now been examined during
algorithm development, and it must not be reused to select hyperparameters
and then claimed as untouched testing.

### Important counterexamples

On 2%-capacity window 0, both seeds simultaneously deteriorate in
actual deadline failures (+8 / +6) AND measured CO2 (+0.13% / +1.22%).
At 10%-capacity window 0, one seed improves the SLA and the other
degrades; carbon falls in both.
At 2%-capacity window 1, seed 1 finishes an additional job under
joint routing: its raw CO2 value **must not** be interpreted as a
comparable per-workload emission improvement.

There is no stable Pareto improvement across settings, and no
statistical uncertainty interval can rescue the tiny two-seed
single-trace design. Results do NOT show any chance-constraint or
formal SLA satisfaction guarantee.

## Mechanism and candidate research hypothesis

The experiment demonstrates that same-batch commitment-aware
lookahead can produce different placement decisions and sometimes
avoid queue competition that the per-task carbon-greedy baseline
fails to account for. However, a fixed 4x8 beam and an optimistic
forecast model can also overcommit or privilege the wrong deadlines
under severe congestion.

A defensible next hypothesis is **congestion/state-adaptive joint
batch scheduling with risk calibration and explicit accepted-work
constraints**, where candidate selection and tuning use only
earlier training/validation windows. Test full-capacity and multiple
independent future workload slices beyond those inspected here.
A width/chunk ablation and explicit workload-pressure regime gate
are needed before moving to learned policies. This remains
independent-task, not DAG workflow, scheduling.

## Scientific status

- Research-only heuristic baseline with reproducible code and CI.
- Observable improvements in one heldout stress regime and
  observed failures in other regimes.
- Not yet a publishable new constrained RL algorithm.
- No evidence that the method provides statistical generalization,
  robust capacity transfer or proven causal improvement in
  production datacenters.
