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
python -m unittest discover -s research_sci -p 'test_*.py' -v
python -m research_sci.run_pilot --steps 8 --drain-steps 24 --seeds 42
```

For exploratory paired multiple-seed checks:

```bash
python -m research_sci.run_pilot --steps 32 --drain-steps 96 --seeds 1 42 2026 --output research_sci/results/pilot_3seeds.json
python -m research_sci.summarize research_sci/results/pilot_3seeds.json
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

## Queue-aware pilot (2026-11-04)

The separate `queue_risk.py` baseline estimates FIFO queue wait by simulating
**currently known** running tasks' release times and pending tasks' resource
demands. This is an optimistic, deterministic estimate, not a calibrated
probability, not a guarantee, and not a forecast of future arrivals. The model
only uses observed task queues; it never reads future carbon traces.

Two additional methods are included:

- `queue_risk_carbon`: carbon-minimizing spatial routing among options where
  predicted completion plus an explicit 30-minute buffer fits SLA;
  otherwise fastest predicted completion.
- `queue_risk_defer`: same queue-aware placement, with causal historical-carbon
  time-shifting only when sufficient buffered slack exists.

Both use the same simulator action mapping as the existing methods. A queue
policy can select a data center currently at capacity if the **known** running
tasks are predicted to release resources before the job arrives; unlike simple
`can_schedule`, this can reveal the scientific relevance of queue estimation.

Capacity-pressure experiments create **temporary scaled data center YAML**
without changing the upstream config file. Scaling is synthetic and must be
labeled as a stress test, NOT as the original benchmark's default hardware.

```bash
python -m unittest discover -s research_sci -p 'test_*.py' -v
python -m research_sci.run_pilot --steps 16 --drain-steps 64 --seeds 1 42 --capacity-scale 0.02 --policies lowest_carbon sla_carbon queue_risk_carbon queue_risk_defer --output research_sci/results/stress_002.json
python -m research_sci.summarize research_sci/results/stress_002.json --reference lowest_carbon
```

**Paper-quality gate:** inspect per-seed matched admissions, unfinished and
overdue counts, measured end-to-end task latency, queue forecast errors, and
confidence intervals before claiming improved SLA reliability or carbon savings.
A 30-minute buffer is an explicit heuristic parameter, not a probabilistic bound.

## Finish-time calibration audit

The optional `--audit-predictions` flag computes a **decision-time** finish
forecast for each actually dispatched task, using current running jobs, FIFO
pending queues, already-in-transit routes and all earlier routes in the same
action batch. It records a task's *first committed dispatch* estimate only.

The audit compares forecast timestamps with task `finish_time` **only after
the simulator reports the task completed**; uncompleted tasks are censored
rather than counted as correct. Forecast-unavailable tasks are separately
counted. Reported outputs include MAE, signed bias (positive means an
optimistically early forecast), 90th-percentile absolute error, the proportion
of completed tasks exceeding the 30-minute forecast buffer, and a
**completed-only** false-safe-SLA rate. Per-task JSONL is stored next to the
results as `<output-stem>_forecasts/<policy>_seed<seed>.jsonl`.

The existing future-arrival exclusion remains important: the model can see
only already-known arrivals; it has no access to the future workload trace.
These are empirical diagnostics, **not calibrated probability bounds**.
Unfinished/censored tasks must be included in any later end-to-end SLA
assessment rather than silently removed. No inference should be made from
calibration on completed-only tasks under heavy censoring.

```bash
python -m research_sci.run_pilot --steps 16 --drain-steps 64 --seeds 1 42 --audit-predictions --capacity-scale 0.02 --policies lowest_carbon sla_carbon queue_risk_carbon queue_risk_defer --output research_sci/results/stress_002.json
```

## Online causal residual calibration (experimental)

Two additional comparison policies are now implemented:

- `queue_calibrated_carbon`: queue-aware carbon placement with a causal
  rolling positive-residual upper quantile as its SLA risk margin.
- `queue_calibrated_defer`: same dynamic risk margin plus history-only
  low-carbon wait decisions when the estimated deadline slack permits it.

The calibrator starts with a **30-minute fallback margin**. Only once at least
20 *completed* jobs have produced actual-vs-first-dispatch prediction residuals
does it use a rolling 256-completion window and the empirical upper order
statistic for target `alpha=0.1`. Every completion update happens **after**
the corresponding simulator step and is available only to future decisions.
The margin used for each actual routing decision is frozen, allowing
prequential (decision-time, no-lookahead) assessment.

```bash
python -m unittest discover -s research_sci -p 'test_*.py' -v
python -m research_sci.run_pilot --steps 16 --drain-steps 64 --seeds 1 42 --audit-predictions --capacity-scale 0.02 --policies lowest_carbon sla_carbon queue_risk_carbon queue_risk_defer queue_calibrated_carbon queue_calibrated_defer --output research_sci/results/stress_calibrated.json
```

The output includes the completed-only **decision-time empirical margin coverage**,
the **buffer-aware false-safe rate**, and the number of calibration-ready
decisions. Censored and unforecasted jobs are separately reported. The
quantile is **NOT conformal / distribution-free coverage**: online policy
feedback, nonstationarity and censoring invalidate an unconditional guarantee.
Its `alpha=0.1` is a heuristic **target**, not a certified 10% violation
bound. Interpret controlled risk only after held-out chronological evaluation.


## Chronologically separated frozen-risk holdout (next pilot)

`chronological_eval.py` is a separate workflow from the existing
same-window online experiments. Two paired treatments are run on **separate
recreated simulators with identical seed and calibration actions**:

- `fixed_30`: fixed 30-minute risk buffer on the later unseen test cohort.
- `precalibrated_frozen`: a 90th-percentile empirical positive completion-time
  residual buffer estimated from **earlier completed jobs only** and frozen
  before the first held-out arrival. Minimum 20 usable training residuals.

The timeline has four consecutive segments:
**16 training-admission ticks -> 128 no-admission drain ticks -> 16 held-out
admission ticks -> 96 held-out drain ticks**. All segments run on one
simulation clock per treatment, without rewinding the forecasted weather,
carbon, workload or resource state. The simulator *must* report zero training
jobs still in progress before held-out admissions begin; otherwise the
experiment fails. A clean-gap test is intentional to isolate the two cohorts.

The evaluator checks matching training-route signatures, matching training
admissions/completions, matching test admission fingerprints and counts,
identical phase boundaries, and no overlap between calibration and held-out
task objects. The learned risk margin is unavailable to the test until
training has finished, and it is never updated from test completion labels.
It writes **test-window-only** carbon and cost, completed/unfinished/overdue
counts, forecast coverage and false-safe rate, plus the count of actual
data-center choices changed in the paired treatments.

```bash
python -m research_sci.chronological_eval --seeds 1 42 \
  --calibration-steps 16 --gap-steps 128 --test-steps 16 \
  --drain-steps 96 --capacity-scale 0.02 \
  --output research_sci/results/chronological.json
```

**Strict limitations:** this is a pilot with just two seeds and one
chronological region, synthetic capacity reduction, and a non-exchangeable
empirical quantile. The 90% target is **not** a coverage guarantee. It is
also a cohort-separation experiment rather than a model trained on a distinct
calendar month; larger disjoint windows and outside-sample workload seasons
are required before publication-level claims.


## Frozen-buffer SLA/carbon descriptive frontier

`risk_frontier.py` compares the following **predeclared** margins on the
same chronological held-out arrivals, after an identical historical warmup
for each seed: 30, 60, 120 minutes and a frozen empirical upper residual
from earlier completed training jobs only.

```bash
python -m research_sci.risk_frontier --seeds 1 42 \
  --calibration-steps 16 --gap-steps 128 --test-steps 16 \
  --drain-steps 96 --capacity-scale 0.02 \
  --output research_sci/results/risk_frontier.json
```

Risk is evaluated as **actual missed deadlines among all admitted test
jobs**, plus overdue unfinished tasks, with unfinished-not-yet-overdue
reported separately. We also report completed-only forecast-error
coverage, the count/fraction of jobs deemed buffered-safe at dispatch
whose actual outcomes can be evaluated, and the false-safe count. An
empty predicted-safe group is **vacuous**; it has a null/undefined
false-safe rate, NOT zero risk.

The output comprises per-treatment JSON/CSV and a compact paired-seed
summary with purely **descriptive** carbon-vs-missed-deadline
non-domination flags. Pareto comparability is disabled for treatments
with different completed task counts. This grid is chosen *before*
seeing test results; do not select a winning margin using the same
test set and subsequently report its test performance as out-of-sample.
Genuine parameter optimization will require a third, separate
validation segment ahead of a held-out test interval.

The synthetic 2%-capacity stress scenario and two-seed evaluation
remain exploratory. Neither the empirical frozen percentile nor the
resulting descriptive frontier is a mathematically certified
SLA-constrained optimizer.


## Three-window nested validation and locked held-out test

The `nested_validation.py` experiment extends the two-window frozen
risk-margin study by using **validation only** for parameter selection.
For each paired seed, four predeclared options (30, 60, 120 minutes and
the earlier training-derived frozen margin) are evaluated on the SAME
validation arrivals. The deterministic selection rule requires **every
validation seed** to show equal numbers of completed jobs and no more
actual deadline misses (including overdue unfinished jobs) than the
30-minute baseline; it then minimizes average validation carbon. If all
other options violate this condition, the selected treatment remains
30 minutes.

After this choice is printed and locked, the simulator is re-created
from the same training start time and advanced to a **later held-out test
arrival window**. Only the fixed-30 baseline and the validation-selected
treatment are evaluated there. Holdout metrics are not read in the
selection function. The script checks identical training route signatures
and matched heldout arrival fingerprints, admission counts, timeline
boundaries and frozen margins for paired treatments.

Default grid: 16 training-admission steps, 128-step gap, 16
validation-admission steps, further 128-step gap, 16 held-out test-admission
steps, 96 heldout drain steps. The heldout replay intentionally skips
validation arrivals during the middle time gap, so it is a controlled
counterfactual on a later clock interval rather than a fully continuous
production environment across train/validation/test.

```bash
python -m research_sci.nested_validation --seeds 1 42 \
  --capacity-scale 0.02 --output research_sci/results/nested_validation.json
```

Output contains validation results, the **pretest locked selection and
rule**, and independent test outcomes, with separate CSVs for validation
and heldout test. This avoids the previous test-set selection issue,
but two seeds, a single synthetic-capacity setting and a deliberately
gapped simulation remain **exploratory** and cannot certify SCI
significance, generalization or SLA probability bounds.

## Predeclared temporal robustness (two held-out windows)

`temporal_robustness.py` reuses the same validation-only choice, then
freezes it **once** before observing either held-out window. It tests
this single margin on **two non-overlapping later time intervals** (by
default starts 288 and 448 simulator ticks after the common start). A
fixed 7-day simulator horizon keeps initial workload generation and
training-prefix configuration identical across all replays.

Each test window is a *separate counterfactual replay* starting from the
same historical training prefix: test #2 intentionally excludes both the
validation cohort and test #1 admissions. This is not a continuous
production trace, and the two windows share a workload source, seeds
and calibrator. Validation selection NEVER sees either held-out outcome.
Every paired replay verifies matching training-task fingerprints, training
routes, test admission fingerprints and completed-work counts.

```bash
python -m research_sci.temporal_robustness --seeds 1 42 \\
  --test-start-ticks 288 448 --capacity-scale 0.02 \\
  --output research_sci/results/temporal_robustness.json
```

CSV and JSON report actual SLA failures, fully completed work, carbon,
positive/negative paired carbon changes per seed and window. A favorable
mean is not a significance claim, and neither an expired or vacuous safe
set nor favorable outcomes in just one window are treated as robust risk
control. Generalization still requires independent workloads, more time
windows, more seeds and realistic hardware and arrival pressure.

## Two-window, multi-capacity robustness stress (exploratory)

The separate `capacity_sensitivity.py` run tests whether a validation
choice transfers across **three predeclared synthetic resource capacity
scales (2%, 5%, 10%)** and **two later time windows**. The selected risk
buffer is chosen **once on the 2%-capacity validation cohort**, frozen,
and never reselected or adjusted from any test result. Same seeds 1 and
42 and fixed seven-day simulator duration are used throughout.

```bash
python -m research_sci.capacity_sensitivity --seeds 1 42 \
  --capacity-scales 0.02 0.05 0.1 --test-start-ticks 288 448 \
  --output research_sci/results/capacity_sensitivity.json
```

Only paired tests at the **same capacity / seed / window** are
compared. All replays omit arrivals from earlier validation and other
test windows; this remains a counterfactual test, not one uninterrupted
production trajectory. Historical calibration is reobserved at each
capacity, which changes the modeled workload pressure; the chosen
margin itself remains locked based on the original 2% validation.

**Crucial new audit:** Equal completed task **counts** are insufficient:
the runner records SHA-256 fingerprints of finished task names,
arrival times, durations and CPU/GPU/memory requirements, plus completed
core-minutes and GPU-minutes. Carbon deltas are `null` unless the actual
completed task *sets* match between paired policies. Raw emissions,
SLA failures, admissions and completions remain available to interpret
a throughput/carbon tradeoff.

Do not compare raw facility+transmission totals **between** capacity
scenarios as if resource configurations were physically identical.
This 2x3x2 grid is a reproducibility stress test; it does not establish
SCI-level significance, a formal risk guarantee, or generality to other
workload datasets.


## Observable pressure vs later forecast residuals (diagnostic only)

`state_risk_audit.py` freezes a **dispatch-time snapshot** before
`env.step` and before adding the target job to known reservations.
Features include observed CPU/GPU/memory utilization; pending/running
queue counts and queued core-minutes; already-in-transit and earlier
same-batch committed work; current carbon intensity; task resource
demand; time to SLA deadline and queue-model optimistic slack.
Actual finish time and violation labels are **never input features**.

After the independent heldout evaluation, `audit_state_risk` joins
snapshots with actually completed outcomes and records unfinished jobs
as **censored**, rather than imputing zero prediction error. It reports
MAE, signed optimism, P90 error, fraction of completed forecast errors
over 30 minutes, and observed SLA misses across *predeclared* pressure
bins (<50%, 50–80%, >=80% CPU utilization; pending queue; known inbound
commitments; negative, 0–60, and >=60 minute predicted SLA slack).

A standalone reproducible observational stress comparison uses the
same synthetic capacity levels and later time windows as earlier
sensitivity work:

```bash
python -m research_sci.state_risk_study --seeds 1 42 \
  --capacity-scales 0.02 0.1 --test-start-ticks 288 448 \
  --output research_sci/results/state_risk_study.json
```

Per-task JSONL contains the frozen state and the *later observed*
completion outcome; the JSON/CSV summaries make the number of
censored, unforecasted and usable tasks explicit. Group comparisons
are descriptive associations, not causation or statistical coverage.
This module **does not tune or introduce a scheduler policy** and
must not be used to choose bins or thresholds from final heldout
errors and then report success on those same observations.


### Decomposing inherently impossible deadlines

The pressure audit additionally records a **necessary SLA feasibility
condition at dispatch**: `deadline - decision_time - task_duration`.
If this quantity is negative, the job cannot meet its SLA even with
instantaneous execution start and zero network transfer. A nonnegative
value is *not* an SLA guarantee because real routing, admission queues
and resource contention add delays. This is a strict lower-bound
diagnostic; it never reads the job's actual completion time or future
tasks.

In the pressure study the two groups are reported alongside later
actual deadline misses. This prevents a good completion-time predictor
from being blamed for deadline violations that were structurally
unavoidable **at dispatch**. It does not prove whether an earlier
dispatch decision could have saved the job, and it does not model
network-latency lower bounds.


## All-datacenter dispatch-time candidate feasibility audit

A new **read-only** experiment audits the full data center action set at
the exact moment a job is routed. `action_feasibility_audit.py` uses
the same 15-minute FIFO queue predictor, observed task/network delay,
current grid intensity, running/pending queues, in-transit tasks and
earlier same-batch commitments as the actual routing policy. The
target job is **not yet committed** when alternative centers are
evaluated, preventing a double-counting reservation.

The audit distinguishes:

- **No forecastable candidate:** Every center's bounded queue forecast
  returns no finish time; this is NOT automatically a proof that the
  job cannot meet its deadline.
- **No forecasted feasible candidate:** No center is *estimated*
  to finish by the deadline (unbuffered and buffered counts separately).
- **Selected route predicted late despite a feasible alternative:**
  The selected center is estimated late, but at least one other
  center is estimated on time. This is a predicted opportunity,
  **NOT a demonstrated avoidable SLA violation**.
- **Buffered feasibility and intensity choice:** Exposes whether
  the chosen route minimizes *observed grid carbon intensity* among
  estimated SLA-feasible centers. It does not claim marginal per-task
  carbon reductions or predict future carbon.

The true completion and SLA label is joined **after** the simulator
horizon and unfinished jobs remain censored. Per-job JSONL includes
candidate completion predictions and the later actual outcome, with
aggregate counts audited against the simulator's real completion
and SLA accounting.

```bash
python -m research_sci.action_feasibility_study --seeds 1 42 \
  --capacity-scales 0.02 0.1 --test-start-ticks 288 448 \
  --output research_sci/results/action_feasibility_study.json
```

This is an **observational one-job-at-a-time counterfactual** with
fixed past commitments. Rerouting one job would alter future
queues/arrivals and must be simulated in a separate matched policy
experiment before an SLA rescue or carbon improvement can be claimed.

## Predeclared queue scheduling ablation: FIFO versus EDF

The experiment `queue_priority_experiment.py` compares the original FIFO
datacenter pending queue with an opt-in **earliest absolute deadline first
(EDF)** queue. Both retain the same chronological training arrivals,
fixed 30-minute risk margin, task-level action space, data-center resource
capacity and incoming test workload. EDF is installed ONLY at the
test-phase boundary; training is FIFO for both treatments.

The research-only wrapper sorts each data center's pending deque just
before its ordinary `SustainDC.step`, AFTER newly arrived in-transit
work is enqueued. The queue-aware finish-time predictor also sorts
known FIFO arrivals by EDF before forecasting. All alternative
placement decisions are thus consistent with the actual queue discipline.
`fifo` is the untouched original default; `main` is not changed.

The comparison is **joint routing+queue discipline**, not an isolated
causal queue-order effect, because changed queue forecasts can change
subsequent data-center routing decisions. EDF is a standard scheduling
baseline and is not itself SCI innovation. Results include true SLA
misses (completed and overdue unfinished), throughput and admitted
work. Only when the actual *identical finished job set* is confirmed
do we report a paired carbon-efficiency delta. We do not select EDF
from these held-out results for re-testing on those same windows.

```bash
python -m research_sci.queue_priority_experiment --seeds 1 42 \
  --capacity-scales 0.02 0.1 --test-start-ticks 288 448 \
  --output research_sci/results/queue_priority.json
```

The predeclared two-window, two-capacity, two-seed stress still uses a
single Alibaba-derived workload trace and gapped counterfactual
replays. Even a favorable result is preliminary, not statistically
validated carbon/SLA superiority or a risk guarantee.


## Diagnostic 2x2 queue execution versus routing forecast factorial

The FIFO-vs-EDF paired experiment revealed that matched EDF+EDF can
**increase actual SLA deadline misses**, especially at 10% synthetic
capacity, even when task completion sets match. Because the earlier
comparison changed both actual pending queue execution order AND the
routing policy's queue forecast simultaneously, it cannot attribute
the effect to either change alone.

The `queue_factorial_ablation.py` script predeclares all four
combinations:

| Actual DC pending queue | Queue forecast used for routing |
| --- | --- |
| FIFO | FIFO (unchanged baseline) |
| EDF | FIFO (execution-order change only relative to baseline) |
| FIFO | EDF (prediction/routing change only relative to baseline) |
| EDF | EDF (matched joint change) |

Mismatch cases are deliberately a *diagnostic*, not recommended
deployment configurations; accurate queue forecasting normally
requires matching the execution rule. The 2x2 contrasts can expose
interactions but do **not** by themselves certify independent causal
effects in a multi-task dynamic system.

```bash
python -m research_sci.queue_factorial_ablation --seeds 1 42 \
  --capacity-scales 0.02 0.1 --test-start-ticks 288 448 \
  --output research_sci/results/queue_factorial.json
```

Both execution and prediction settings are installed only at heldout
test start; all earlier training tasks and routing history use FIFO.
All four variants share seeds, actual test arrivals, calendar time and
capacity. The full simulator recomputes each route and future queue
state; real SLA misses, unfinished overdue jobs, and CO2 are measured.
Paired CO2 delta is null unless *exactly the same jobs finish*. These
are exploratory same-trace synthetic stress results and no
out-of-sample learning or novel EDF algorithm is claimed.

## Bounded joint batch assignment pilot (FIFO queue preserved)

`joint_batch.py` and `joint_batch_study.py` introduce a **predeclared
deterministic 4-beam / 8-task-chunk lookahead** over the current visible
task batch. The original FIFO execution queue and its FIFO
`predict_finish` model remain unchanged in BOTH arms. Training is
identical in both. The beam carries branch-specific reservations for
known in-transit jobs and earlier assignments; each branch checks all
available centers and keeps the four best partial assignments in the
**actual environment action order**.

The lexicographic objective first minimizes optimistic predicted
deadline misses, then summed predicted lateness, then predicted risk
buffer shortfalls, and finally a *CPU/GPU/memory work-weighted CURRENT
carbon intensity proxy*. This proxy is NOT simulated marginal facility
or network carbon emissions and gives no calibrated SLA guarantee.
Prediction is arrival-blind beyond currently known commitments.

```bash
python -m research_sci.joint_batch_study --seeds 1 42 \
  --capacity-scales 0.02 0.1 --test-start-ticks 288 448 \
  --output research_sci/results/joint_batch_study.json
```

Eight paired simulator scenarios use the same seeds, arrivals,
original-capacity mapping, seven-day duration, and train/test
chronological separation. Neither beam width nor chunk size is
tuned on heldout. We compare true SLA failures including overdue,
completed-job identities/throughput, actual total facility+network
emissions and route changes. No carbon-efficiency percentage is
reported when exact finished job sets differ.

**Scope limitation:** bounded beam search and separate chunks are
not optimal whole-batch search; prefix queue forecasts can miss
interaction effects from later tasks and later exogenous arrivals.
The algorithm is a research heuristic baseline, not a novel RL
method or SCI result by itself. Any comparative improvement requires
independent broader workload validation.
