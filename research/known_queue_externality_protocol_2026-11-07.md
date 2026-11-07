# Observable queue externality probe: instrumentation-only protocol

2026-11-07. This is a **diagnostic code artifact**, NOT a new validated NSGA-II scheduling policy.

## Motivation and baseline

In the full, successful lagged-PUE task-level paired audit, some tasks that were **not rerouted** had different observed start and finish times and changed SLA labels after other tasks were rerouted. See https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42371389941. This is consistent with shared-resource interactions, but observational paired comparisons alone do **not** establish causal network/queue externalities.

The latest cached-front taskwise selector did not jointly improve carbon and SLA in any of four congestion development pairs, despite a single-search optimizer budget. The complete negative result is recorded in `research/lagged_pue_front_taskwise_negative_findings_2026-11-07.md`.

## Mechanism implemented and exact observability

`research/known_queue_externality.py` provides an *unintegrated* diagnostic pair of functions:

- `project_tracked_starts`: project **currently known** pending FIFO, committed in-transit and hypothetically new arrivals under the same 15-minute queue abstraction as the existing predictor; track start times of both new and existing tasks.
- `known_queue_externality`: compare **no new batch dispatched** vs **a specified proposed dispatch**, while keeping current committed in-transit arrivals, running tasks and queued pending tasks identical. Record number of existing tasks with delayed starts, total extra predicted waiting, and additional predicted tardiness. It is a counterfactual *within the predictor*, not validated physical or causal treatment effect.

No future workload admissions, future carbon observations, realized post-action outcomes or unseen task arrivals are inputs. The probe is not automatically called inside GA fitness and has not changed the research policy's actions, optimizer request counts, or official simulation outcomes.

## Strict next scientific gates

1. Unit tests must cover delayed already-committed transit task, duplicate identity, capacity rejection, no-op and matching against the original existing FIFO predictor.
2. If those tests pass, observe the probe at completed **predecision** queue states of previously explored workload dates with frozen actions and compare to realized subsequent queue changes. Do not infer performance from synthetic unit tests.
3. If the predicted signal is measurable, next consider an **ablation** that incorporates committed-task delay into the *single-search* tardiness surrogate. That would increase per-evaluation projection work and needs separate wall-time, physical carbon and actual SLA audits.
4. Validate noninterference: a measurement-only run must preserve the exact same task destinations, arrival identities, completion timestamps and energy accounting as its noninstrumented comparator.
5. Only after development/falsification on explored dates should any algorithm be frozen and evaluated on genuinely untouched calendar workloads.

Caveats: The simulator queue predictor is a discrete approximation with known potential forecast error, not a formal worst-case SLA guarantee. The tool's input has identity-hashable tasks, nonnegative resource requirements, and fixed known finish times for running tasks. Physical energy from scheduler CPU work is not measured. Independent cloud tasks, **not DAG workflows**, are modeled.
