# Research baseline verification (independent branch)

This directory is an **initial verification scaffold**, not an end-to-end
reproduction or a claim that any scheduling algorithm is scientifically valid.

## Current scope
- `research/tests/test_rule_based_baselines.py`: small deterministic
  selector-level tests using mocked data centers, with no workload dataset.
- `research/tests/test_environment_factory_contract.py`: guards the
  simulator configuration forwarding path in `train_rl_agent.make_env`.
- `research/tests/test_reward_signal_contracts.py`: characterizes how the
  original cost/carbon reward components consume task proxies instead of
  recorded simulator metrics. These tests are expected to **pass** while
  demonstrating a measurement mismatch.
- `research/unified_baseline_smoke.py`: runs the existing baseline selector implementations
  through a common per-task environment action pathway with transmission delay.
- CI compiles three critical Python modules, runs selector/adapter tests, and
  runs both native and adapted short full-simulator checks.
- The upstream physics, datasets, policy implementations, and YAML defaults
  remain unchanged. One targeted change to `train_rl_agent.py` now forwards
  `sim_cfg` into `TaskSchedulingEnv`, which previously silently ignored the
  YAML action/defer flags during environment construction.

## Task-level SLA validation and EDF comparator

- `research/task_sla_audit.py` independently recomputes SLA from task
  `finish_time <= sla_deadline`, checking arrival/start/finish order,
  execution duration, and the simulator's recorded SLA flag. It reports mean
  and P95 response/wait times and positive tardiness in minutes.
- `edf_sla_carbon` is a **priority-order baseline**, not a novel algorithm:
  it sorts each dispatch batch by the *absolute deadline* before applying
  the same spatial SLA-feasible low-carbon selector. As routing waits and
  FIFO queueing matter, this is a useful check of priority benefits.
- `batch_unified_baselines.py` outputs
  `unified_batch_completed_tasks.csv` alongside run-level JSON/CSV and
  summaries. CSV contains task timestamps and recomputed SLA status.
- Each simulation includes a fixed admission horizon followed by drain
  steps. We preserve the count of outstanding and overdue unfinished tasks.
  Any nonzero leftovers invalidate a claimed **completed-cohort** result.
- The tests audit internal consistency, *not* real-world physical calibration.
  Three seeds and one load window are insufficient to claim significance or
  publish a general algorithm ranking.

## Verified paired-task exploratory finding (2026-11-04)

From GitHub Actions run [41778053806](https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41778053806),
five comparators × three seeds completed successfully with 776 tasks per run,
no outstanding queue/running/transfer tasks, and **49/49** research contract tests.

The exported `unified_batch_completed_tasks.csv` was independently matched by
`(seed, arrival_utc, job_name)`. Task IDs and arrival/deadline/resource
characteristics are aligned across the matched baselines.

- Against `lowest_carbon`, `sla_feasible_carbon` rescued respectively
  16, 16, and 12 deadline misses for seeds 1, 42, and 2026, while harming
  0 matched tasks in these particular trials.
- Its violated-task counts were 128/776 in each seed, versus
  144/776, 144/776, and 140/776 for `lowest_carbon`.
- `edf_sla_carbon`, which only sorts same-timestep dispatch batches by
  absolute deadline, produced **identical per-task** destination, start time,
  finish time, and SLA to `sla_feasible_carbon` for all three seeds.
  This is a *negative result*: it is **not** an independent competitive
  baseline in this configuration. A queue-level EDF design would add different
  control capability and require its own fairness protocol, not be silently
  substituted.
- These are three correlated seeded simulator conditions, **not**
  proof of generalization, statistical significance, or physical validity.
  Longer admission windows and independent workload/date scenarios are needed.

`research/paired_task_analysis.py` now automates this cohort-consistency
check and writes a per-seed rescue/harm report to Actions artifacts.

## Important audit findings before comparing algorithms
1. `utils/task_assignment_strategies.py` has multiple original strategies.
   `lowest_price`, `lowest_carbon`, and `most_available` consult
   `can_schedule(task)`, whereas `round_robin` and `least_pending` do
   **not**. This difference is documented in tests, not silently corrected.
2. The fork's current `configs/env/sim_config.yaml` has
   `disable_defer_action: true` and `single_action_mode: true`.
   Under this configuration, learned agents cannot use deferral, and a
   single decision is shared across tasks. `train_rl_agent.make_env` originally
   failed to forward these flags to the environment; this branch fixes that
   specific factory defect. Other training entrypoints still require audit.
   Action sets must be normalized before comparing task-level deferral policies.
3. The original `EnergyPriceReward` and `CarbonEmissionsReward` do not
   read actual `cluster_info` energy/cost/emissions, network costs, or
   SLA statistics; they use `cores_req * duration / 10000` proxies.
   Their unit/calibration relationship to the simulator is not established.
   Reward-based rankings cannot be presumed equivalent to rankings based
   on actual operational outcomes.
4. The original `train_rl_agent.py` test invokes a subprocess via
   `os.system(...)` and does not check the exit status, allowing a false
   positive if training fails. The original three tests passing is not
   a scientific validation.
5. The rule-based routing path enqueues assignments directly in the
   destination's pending queue, while the manual RL environment explicitly
   puts assigned tasks into `in_transit_tasks` after delay. This is a
   suspected algorithm-comparison asymmetry requiring direct reproduction.
   `unified_baseline_smoke.py` supplies an **adapted** RBC comparison under
   `manual_rl` so all chosen routes enter the same `in_transit_tasks` queue.
   It is not equivalent to native RBC mode: the adapter counts fallback
   decisions when the upstream strategy returns no valid destination.
   Run both modes and explicitly label which experiment was used.
6. Lightweight contract tests do not validate execution completion, SLA
   penalties, network transmission, energy, carbon, or cross-seed
   repeatability. A full simulation audit remains mandatory.

## Next reproducibility gates
- Fix and record a simulator commit SHA and a single experiment configuration.
- Validate a hand-constructed task trace with independent accounting.
- Run original rule-based schedulers with matched dates, seeds, workload,
  capacity, and objective measurement. Export per-run raw results.
- Add SLA-aware, time-shifting, multi-objective and RL baselines only after
  the environment and measurement protocol are validated.
- Compare algorithms using identical legal action sets or disclose and
  isolate their different control capabilities.

## Execute locally
```bash
python -m pip install numpy pandas
python -m compileall -q utils/task_assignment_strategies.py envs/task_scheduling_env.py simulation/cluster_manager.py
python -m unittest discover -s research/tests -p 'test_*.py' -v
```

**Scientific status:** Full-simulator short smoke is executable, but not a
paper-grade comparison. The unified adapter is currently under verification;
long-window accounting and invariants remain to be validated.

**Scientific status:** The new SLA and EDF experimental checks are being verified in CI. Full paper-grade validation, several workload/date regimes, independent objective accounting, and stronger baselines remain open.
