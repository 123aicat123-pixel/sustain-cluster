"""Lagged-PUE taskwise deadline-risk guard with an online shadow baseline.

This is a *development hypothesis*, not a proven SLA or carbon guarantee.
The shadow reference is computed with the same currently observable state
and its own seeded legacy NSGA-II. No future workload, real emissions or
post-decision facility telemetry is accessed. Unlike the original PUE
candidate, this policy performs TWO separate genetic optimizations per
nonempty batch: both search budgets must be reported.
"""
from __future__ import annotations

from research.queue_aware_nsga2 import QueueAwareLaggedPUE, QueueAwareIndexedTransit


def choose_if_nonlater(tasks, candidate, shadow, candidate_starts, shadow_starts):
    """Accept PUE candidate only if no predicted task start is later.

    Durations are immutable for matched tasks, so nonlater start implies
    nonlater predicted finish *within the same queue predictor*. This is
    not a guarantee about future workload arrivals or realized deadlines.
    """
    if not tasks or len(candidate) != len(tasks) or len(shadow) != len(tasks):
        raise AssertionError("inconsistent nonempty candidate and shadow cohorts")
    if len(set(tasks)) != len(tasks):
        raise AssertionError("duplicated task in risk-gate cohort")
    if set(tasks) - set(candidate_starts) or set(tasks) - set(shadow_starts):
        raise AssertionError("unpredicted task start in risk gate")
    late = sum(candidate_starts[task] > shadow_starts[task] for task in tasks)
    return (list(shadow) if late else list(candidate)), bool(late), late


class QueueAwareLaggedPUEShadowGuard(QueueAwareLaggedPUE):
    """Compare full PUE candidate with an online PUE-blind NSGA-II shadow.

    The shadow's search is an additional computational cost. The guard
    uses actual online queue *predictions*, not realized task outcomes.
    """

    def reset(self):
        super().reset()
        self._shadow = QueueAwareIndexedTransit(
            seed=self.seed, population=self.population,
            generations=self.generations, delay_fn=self.delay_fn,
        )
        self.shadow_evaluation_requests = 0
        self.shadow_surrogate_evaluations = 0
        self.shadow_planner_projection_calls = 0
        self.shadow_planner_projection_seconds = 0.0
        self.risk_guard_checks = 0
        self.risk_guard_reversions = 0
        self.risk_guard_late_tasks = 0
        self.risk_guard_blocked_route_changes = 0

    def set_context(self, now, manager):
        super().set_context(now, manager)
        self._shadow.set_context(now, manager)

    def set_in_transit(self, in_transit_items, datacenters):
        super().set_in_transit(in_transit_items, datacenters)
        self._shadow.set_in_transit(in_transit_items, datacenters)

    def select_batch(self, tasks, datacenters):
        if not tasks:
            return super().select_batch(tasks, datacenters)
        before_requests = self._shadow.evaluation_requests
        before_unique = self._shadow.surrogate_evaluations
        before_projections = self._shadow.planner_projection_calls
        before_seconds = self._shadow.planner_projection_seconds
        shadow_actions, shadow_fallbacks = self._shadow.select_batch(
            tasks, datacenters
        )
        self.shadow_evaluation_requests += (
            self._shadow.evaluation_requests - before_requests
        )
        self.shadow_surrogate_evaluations += (
            self._shadow.surrogate_evaluations - before_unique
        )
        self.shadow_planner_projection_calls += (
            self._shadow.planner_projection_calls - before_projections
        )
        self.shadow_planner_projection_seconds += (
            self._shadow.planner_projection_seconds - before_seconds
        )

        candidate_actions, candidate_fallbacks = super().select_batch(
            tasks, datacenters
        )
        if shadow_fallbacks != candidate_fallbacks:
            raise AssertionError("candidate and shadow do not share action feasibility")
        chosen, reverted, delayed = choose_if_nonlater(
            tasks, candidate_actions, shadow_actions,
            self.predicted_start_by_task, self._shadow.predicted_start_by_task,
        )
        self.risk_guard_checks += 1
        self.risk_guard_reversions += int(reverted)
        self.risk_guard_late_tasks += delayed
        if reverted:
            self.risk_guard_blocked_route_changes += sum(
                a != b for a, b in zip(candidate_actions, shadow_actions)
            )
            # Observational queue-start audit must describe CHOSEN actions,
            # not the PUE proposal that was vetoed.
            for task in tasks:
                self.predicted_start_by_task[task] = (
                    self._shadow.predicted_start_by_task[task]
                )
        return chosen, candidate_fallbacks
