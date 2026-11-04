# Research baseline verification (independent branch)

This directory is an **initial verification scaffold**, not an end-to-end
reproduction or a claim that any scheduling algorithm is scientifically valid.

## Current scope
- `research/tests/test_rule_based_baselines.py`: small deterministic
  selector-level tests using mocked data centers, with no workload dataset.
- `research/tests/test_reward_signal_contracts.py`: characterizes how the
  original cost/carbon reward components consume task proxies instead of
  recorded simulator metrics. These tests are expected to **pass** while
  demonstrating a measurement mismatch.
- CI compiles three critical Python modules and runs these selector tests.
- The upstream simulator, its datasets, configs, and original policies are
  deliberately unchanged at this stage.

## Important audit findings before comparing algorithms
1. `utils/task_assignment_strategies.py` has multiple original strategies.
   `lowest_price`, `lowest_carbon`, and `most_available` consult
   `can_schedule(task)`, whereas `round_robin` and `least_pending` do
   **not**. This difference is documented in tests, not silently corrected.
2. The fork's current `configs/env/sim_config.yaml` has
   `disable_defer_action: true` and `single_action_mode: true`.
   Under this configuration, learned agents cannot use deferral, and a
   single decision is shared across tasks. This must be normalized before
   comparing task-level deferral policies.
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
python -m pip install numpy
python -m compileall -q utils/task_assignment_strategies.py envs/task_scheduling_env.py simulation/cluster_manager.py
python -m unittest discover -s research/tests -p 'test_*.py' -v
```

**Scientific status:** Not yet reproduced. No baseline performance numbers
should be quoted until a full and independently checked simulation runs.
