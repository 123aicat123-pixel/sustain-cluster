# Initial matched-host planner overhead audit — 2026-11-05

**Status:** verified single GitHub Actions smoke, not a multi-host confidence interval or publishable latency ranking.

Successful workflow: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41990292032
Raw archive: https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41990292032/artifacts/13397701711

The workload was Alibaba May 19, synthetic 5% CPU capacity, seed 901, 16 admission steps and 112 drain steps. All three methods dispatched/completed 417 tasks and recorded 15 nonempty planner calls. The reported timing excludes `env.step`, workload loading and audit operations, and is therefore **scheduler decision wall time**, not end-to-end response time.

| Method | P50 decision ms | P95 decision ms | Mean ms / dispatched task | Search evaluation requests |
| --- | ---: | ---: | ---: | ---: |
| SLA-Carbon heuristic | 0.4534 | 3.0054 | 0.03097 | 0 |
| Queue-NSGA-II | 37.8994 | 180.1218 | 2.04643 | 6000 |
| With-Transit NSGA-II | 40.9788 | 233.2959 | 2.44794 | 6000 |

With-Transit has **29.52%** higher P95 dispatch time and **19.62%** higher mean time per dispatched task than Queue-NSGA-II in this single run. These are descriptive observations, not a general complexity or reproducibility estimate. The number of unique chromosomes may differ even if optimizer evaluation *requests* match.

The same run reported Queue-NSGA-II total cost USD 1166.890 and carbon 3179.466 kg; With-Transit USD 1168.505 and carbon 3184.295 kg. Carbon rises +4.829 kg and cost +1.615 USD in this scenario. Full output, including SLA misses and task rows, is in the archive. These figures are **not** adjusted for any measured environmental carbon cost of the algorithm's own CPU execution.

## Interpretation and next checks

1. Do not compare SLA-Carbon search requests with an NSGA-II request budget as though equal work: it is a simpler heuristic baseline.
2. Repeat matched-host timing with warm-up, independent dates, multiple repetitions, and process ordering controls. Github-host load can dominate short runtimes.
3. Report both P95 and per-task throughput as workload batch size affects latency distributions.
4. Evaluate whether adaptive projection avoids expensive with-transit queue simulation in low-contention states without changing actual SLA/carbon conclusions.
5. No latency 'speedup' claim is supported by this single run. Under the present condition With-Transit is slower.
6. Existing independent-task admission semantics do not amount to a DAG workflow benchmark.

## CI regression encountered and addressed

A separate baseline-contract workflow at https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41990291722 failed *only* in the newly introduced `test_planner_batch_summary` import path because that test indirectly imported `yaml` in a lightweight no-simulator-dependency contract runner. Full-simulator smoke in that workflow succeeded. Commit `fec620a68df665a17615cd8aa532528e810ae36e` changes the test to execute the actual pure summary source via AST, avoiding optional simulator imports. Independent CI confirmation is still necessary.
