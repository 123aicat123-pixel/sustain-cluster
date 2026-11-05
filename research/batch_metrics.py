"""Dependency-free experiment summary metrics for light CI tests."""
from __future__ import annotations
import statistics

METRICS = (
    "reported_total_cost_usd", "reported_total_carbon_kg",
    "facility_energy_kwh", "tasks_seen", "tasks_started",
    "tasks_finished", "sla_met", "sla_violated",
    "pending_last", "running_last", "in_transit_last",
    "local_dispatches", "remote_dispatches",
    "cpu_capacity_scale", "completion_fraction", "fallback_fraction",
    "undispatched_at_horizon", "fallback_assignments",
    "unfinished_dispatched", "unfinished_overdue_at_horizon",
    "task_audit_sla_violation_rate", "task_audit_response_mean_minutes",
    "task_audit_response_p95_minutes", "task_audit_wait_p95_minutes",
    "task_audit_total_tardiness_minutes",
    "planner_dispatch_calls", "planner_dispatched_tasks",
    "planner_dispatch_seconds", "planner_dispatch_mean_ms",
    "planner_dispatch_p50_ms", "planner_dispatch_p95_ms",
    "planner_dispatch_max_ms", "planner_dispatch_ms_per_task",
    "nsga2_surrogate_evaluations", "nsga2_evaluation_requests",
    "planner_projection_calls", "planner_projection_seconds",
    "adaptive_gate_seconds",
)


def summarize(results):
    groups = {}
    for row in results:
        groups.setdefault(row["policy"], []).append(row)
    summary = {}
    for policy, runs in groups.items():
        metrics = {}
        for metric in METRICS:
            values = [float(r[metric]) for r in runs if r.get(metric) is not None]
            if not values:
                metrics[metric] = {"mean": None, "std": None, "min": None, "max": None}
                continue
            metrics[metric] = {
                "mean": statistics.mean(values),
                "std": statistics.stdev(values) if len(values)>1 else None,
                "min": min(values), "max": max(values),
            }
        summary[policy] = {"number_of_seeds": len(runs), "metrics": metrics}
    return summary

