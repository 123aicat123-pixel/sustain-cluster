"""Pre-decision queue-pressure snapshots and *post-outcome* forecast audit.

Predictor features below are strictly observable before env.step. Actual
finish_time, completion/SLA outcomes, future arrivals and future carbon traces
are NEVER read by snapshot_decision. The follow-up aggregate is descriptive,
stratified by PREDECLARED utilization, queue and deadline bins. It is NOT a
causal effect estimate, validated classifier or risk guarantee.
"""
import math


def _finite(value, label):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite " + label)
    return number


def _ratio(used, total):
    total = _finite(total, "capacity")
    if total <= 0:
        raise ValueError("Capacity must be positive")
    used = _finite(used, "used")
    if used < -0.000001 or used > total + 0.000001:
        raise ValueError("Available resources outside total capacity")
    return min(1.0, max(0.0, used / total))


def snapshot_decision(task, dc, now, prediction, commitments,
                      margin_minutes=30.0):
    """Capture known state for ONE chosen DC, before this job is committed.

    commitments contains *earlier* in-transit routes/same-batch choices for
    this center, as (eta, task) pairs, but must not include current task.
    """
    if any(other is task for _, other in commitments):
        raise AssertionError("Target task already in visible commitments")
    totals = (
        ("cpu", dc.total_cores, dc.available_cores),
        ("gpu", dc.total_gpus, dc.available_gpus),
        ("mem", getattr(dc, "total_mem_GB", getattr(dc, "total_mem", None)),
         dc.available_mem),
    )
    occupancy = {
        name: _ratio(_finite(total, name) - _finite(available, name), total)
        for name, total, available in totals
    }
    minutes_left = (task.sla_deadline - now).total_seconds() / 60
    optimistic_slack = (
        (task.sla_deadline - prediction).total_seconds() / 60
        if prediction is not None else None
    )
    if _finite(margin_minutes, "risk margin") < 0:
        raise ValueError("Risk margin must be nonnegative")
    current_intensity = _finite(
        dc.get_current_carbon_intensity(norm=False), "observed carbon intensity"
    )
    if current_intensity < 0:
        raise ValueError("Negative carbon intensity")
    if _finite(task.duration, "duration") < 0:
        raise ValueError("Negative task duration")
    pending = list(dc.pending_tasks)
    running = list(dc.running_tasks)
    committed = [other for _, other in commitments]
    return {
        "task_name": str(task.job_name),
        "dc_id": int(dc.dc_id),
        "decision_time": now.isoformat(),
        "forecast_finish": prediction.isoformat() if prediction else None,
        "risk_buffer_minutes": float(margin_minutes),
        "cpu_util_fraction": occupancy["cpu"],
        "gpu_util_fraction": occupancy["gpu"],
        "mem_util_fraction": occupancy["mem"],
        "current_pending": len(pending),
        "current_running": len(running),
        "known_inbound": len(committed),
        "known_inbound_core_minutes": sum(
            _finite(t.cores_req, "committed CPU") *
            _finite(t.duration, "committed duration") for t in committed
        ),
        "pending_core_minutes": sum(
            _finite(t.cores_req, "pending CPU") *
            _finite(t.duration, "pending duration") for t in pending
        ),
        "time_until_sla_minutes": minutes_left,
        "predicted_sla_slack_minutes": optimistic_slack,
        "observed_carbon_intensity": current_intensity,
        "task_duration_minutes": float(task.duration),
        "task_cpu_fraction_of_dc": _finite(task.cores_req, "task CPU") /
                                   float(dc.total_cores),
        "task_gpu_demand": _finite(task.gpu_req, "task GPU"),
    }


def state_bands(snapshot):
    """Fixed thresholds, deliberately NOT tuned on observed errors."""
    utilization = snapshot["cpu_util_fraction"]
    cpu = ("under_50pct" if utilization < .5 else
           "50_to_80pct" if utilization < .8 else "at_least_80pct")
    slack = snapshot["predicted_sla_slack_minutes"]
    return {
        "cpu_utilization": cpu,
        "pending_queue": "pending" if snapshot["current_pending"] else "empty",
        "committed_inbound": "inbound" if snapshot["known_inbound"] else "none",
        "predicted_sla_slack": (
            "no_forecast" if slack is None else
            "negative" if slack < 0 else
            "0_to_60min" if slack < 60 else "at_least_60min"
        ),
    }


def _group_report(items):
    errors = [record["forecast_error_minutes"] for record in items
              if record["forecast_error_minutes"] is not None]
    n = len(errors)
    ordered = sorted(errors)
    abs_ordered = sorted(abs(v) for v in errors)
    completed = sum(1 for record in items if record["completed"])
    missed = sum(1 for record in items
                 if record["completed"] and not record["actual_met_sla"])
    return {
        "dispatches": len(items),
        "completed": completed,
        "censored_unfinished": len(items) - completed,
        "forecast_evaluable": n,
        "forecast_missing": sum(1 for r in items if r["forecast_finish"] is None),
        "actual_sla_misses_completed": missed,
        "completed_only_sla_miss_rate": missed / completed if completed else None,
        "forecast_mae_minutes": (
            sum(abs(v) for v in errors) / n if n else None
        ),
        "forecast_signed_optimism_minutes": sum(errors) / n if n else None,
        "forecast_p90_absolute_error_minutes": (
            abs_ordered[math.ceil(.9*n)-1] if n else None
        ),
        "forecast_p90_signed_error_minutes": (
            ordered[math.ceil(.9*n)-1] if n else None
        ),
        "error_exceeds_30_minutes_fraction_completed_forecasted": (
            sum(v > 30 for v in errors) / n if n else None
        ),
    }


def audit_state_risk(snapshots, finished_tasks):
    """Join pre-decision features with observed task outcomes only afterward."""
    finished = set(finished_tasks)
    observations = []
    for task, state in snapshots.items():
        complete = task in finished
        actual = getattr(task, "finish_time", None) if complete else None
        if complete and actual is None:
            raise AssertionError("Completed task missing finish_time")
        if state["forecast_finish"] is None or actual is None:
            error = None
        else:
            from datetime import datetime
            predicted = datetime.fromisoformat(state["forecast_finish"])
            error = (actual - predicted).total_seconds() / 60
            if not math.isfinite(error):
                raise ValueError("Invalid prediction residual")
        outcome = {
            **state,
            "completed": complete,
            "actual_finish": actual.isoformat() if actual is not None else None,
            "actual_met_sla": (actual <= task.sla_deadline) if complete else None,
            "forecast_error_minutes": error,
        }
        observations.append(outcome)
    strata = {}
    for feature in ("cpu_utilization","pending_queue",
                    "committed_inbound","predicted_sla_slack"):
        groups = {}
        for record in observations:
            value = state_bands(record)[feature]
            groups.setdefault(value, []).append(record)
        strata[feature] = {
            key: _group_report(records) for key, records in sorted(groups.items())
        }
    return {
        "total": _group_report(observations),
        "by_predeclared_pressure": strata,
        "warning": (
            "Associations only. Predictions assessed on completed jobs are "
            "selection-biased under censoring; no causal inference or "
            "probabilistic SLA guarantee. Pre-decision state is leak-free."
        ),
    }, observations
