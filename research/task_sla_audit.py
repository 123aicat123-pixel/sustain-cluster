"""Independent task-level SLA audit for the research branch.

The simulator records an SLA flag upon completion. This module recomputes the
result from raw task timestamps and verifies the flag and completion duration.
It intentionally does not equate a zero currently-observed violation count
with all admitted jobs meeting deadlines: unfinished jobs are tracked separately.
"""
from __future__ import annotations

import math
from statistics import mean


def _minutes(delta):
    value = delta.total_seconds() / 60.0
    if not math.isfinite(value):
        raise AssertionError("nonfinite task time delta")
    return float(value)


def _percentile(values, percentile):
    if not values:
        return None
    xs = sorted(float(x) for x in values)
    rank = (len(xs) - 1) * percentile / 100.0
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    return xs[lower] * (upper - rank) + xs[upper] * (rank - lower) if lower != upper else xs[lower]


def analyze_finished_tasks(finished, horizon_time):
    """Return (aggregated metrics, per-task rows) for observed completions.

    `horizon_time` is the clock after the final simulator step.
    All measurements are based on each object's arrival/start/finish/deadline
    timestamps, with no reward-function proxy.
    """
    records = []
    response = []
    waiting = []
    lateness_positive = []
    violated = 0
    # Sorting makes detailed CSV output stable for identical traces.
    ordered = sorted(
        finished, key=lambda t: (t.arrival_time, str(t.job_name))
    )
    for index, task in enumerate(ordered):
        if task.start_time is None or task.finish_time is None:
            raise AssertionError("completed task has no execution timestamps")
        if not (
            task.arrival_time <= task.start_time <= task.finish_time
            and task.arrival_time <= task.sla_deadline
            and task.finish_time <= horizon_time
        ):
            raise AssertionError(f"invalid timeline for task {task.job_name}")
        execution_minutes = _minutes(task.finish_time - task.start_time)
        if abs(execution_minutes - float(task.duration)) > 1e-5:
            raise AssertionError(f"execution duration mismatch for {task.job_name}")
        wait_minutes = _minutes(task.start_time - task.arrival_time)
        response_minutes = _minutes(task.finish_time - task.arrival_time)
        late_minutes = _minutes(task.finish_time - task.sla_deadline)
        recomputed_met = task.finish_time <= task.sla_deadline
        if bool(task.sla_met) != recomputed_met:
            raise AssertionError(f"recorded SLA flag mismatch for {task.job_name}")
        violated += int(not recomputed_met)
        waiting.append(wait_minutes)
        response.append(response_minutes)
        lateness_positive.append(max(0.0, late_minutes))
        records.append({
            "task_row": index,
            "job_name": str(task.job_name),
            "origin_dc_id": task.origin_dc_id,
            "dest_dc_id": task.dest_dc_id,
            "arrival_utc": task.arrival_time.isoformat(),
            "start_utc": task.start_time.isoformat(),
            "finish_utc": task.finish_time.isoformat(),
            "deadline_utc": task.sla_deadline.isoformat(),
            "duration_minutes": float(task.duration),
            "waiting_minutes": wait_minutes,
            "response_minutes": response_minutes,
            "lateness_minutes": late_minutes,
            "positive_lateness_minutes": max(0.0, late_minutes),
            "sla_met": recomputed_met,
        })
    completed = len(records)
    summary = {
        "task_audit_completed": completed,
        "task_audit_violated": violated,
        "task_audit_sla_violation_rate": violated / completed if completed else None,
        "task_audit_response_mean_minutes": mean(response) if response else None,
        "task_audit_response_p95_minutes": _percentile(response, 95),
        "task_audit_wait_mean_minutes": mean(waiting) if waiting else None,
        "task_audit_wait_p95_minutes": _percentile(waiting, 95),
        "task_audit_total_tardiness_minutes": sum(lateness_positive),
        "task_audit_late_p95_minutes": _percentile(lateness_positive, 95),
    }
    return summary, records
