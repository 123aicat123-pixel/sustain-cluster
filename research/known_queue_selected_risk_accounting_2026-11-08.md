# Selected-action queue-risk accounting extension (2026-11-08)

The Known-Queue Risk pilot (protocol `research/lagged_pue_known_queue_protocol_2026-11-07.md`) runs on previously explored Jan 20 / Apr 15 CPU=5% scenarios. Its original GitHub Actions run at https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/42383695134 was queued at last check; **no outcome or speedup has yet been established**.

## Auditable extension before any outcome

In addition to counting all objective fitness-side externality projections, the policy now keeps a per-decision mapping of **GA-evaluated chromosome -> known-queue added predicted tardiness (minutes)**. It then attributes the final chosen chromosome's value without performing extra fitness calls. New fields:
- `known_queue_selected_penalty_minutes` — summed selected-action *predicted* additional tardiness for known pre-existing tasks.
- `known_queue_selected_positive_batches` — number of dispatch batches whose final action has positive predicted externality.
- `known_queue_selected_decisions` — number of nonempty decisions with selected chromosome accounting.

The updated experiment audit requires `known_queue_selected_decisions == planner_dispatch_calls` and nonnegative finite, count-consistent accounting. Added reset checks isolate the metric across independent seeds. These fields **do not change the fitness objectives or selected actions**; they only make the selected-action mechanism interpretable.

This study must **not** claim (1) no future workload, (2) formal causal queue externalities from realized task records, (3) real-world emissions improvements, (4) equal total CPU compute just because GA requests match. Physical simulator carbon and realized SLA remain the outcome metrics.

**Interpretation gate:** if selected actions almost always have zero positive externality, extra search cost may be wasted and the penalty mechanism was not relevant to those conditions. If positive externality remains large or SLA worsens, the current objective is not sufficient. Keep all unfavorable cases in the record.
