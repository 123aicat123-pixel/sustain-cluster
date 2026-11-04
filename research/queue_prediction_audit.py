"""Evaluate queue start-time forecast errors against completed tasks.

Predictions are captured at dispatch from information available *then*;
realized start timestamps are read only after simulator execution.
This is an error audit, not a causal proof of forecasting failure.
"""
from __future__ import annotations

import math
from statistics import mean
from datetime import timedelta


def audit_forecasts(finished, predictions, *, seed, policy):
    """Return summary and task-level rows, refusing missing predictions."""
    completed = list(finished)
    errors = []
    detailed = []
    for task in completed:
        if task not in predictions:
            raise AssertionError("completed task lacks dispatch-time prediction")
        expected = predictions[task]
        actual = task.start_time
        if expected is None or actual is None:
            raise AssertionError("missing start timestamp")
        error_minutes = (actual - expected).total_seconds() / 60.0
        if not math.isfinite(error_minutes):
            raise AssertionError("nonfinite start residual")
        is_remote = task.dest_dc_id != task.origin_dc_id
        # Both values compare the identical known task duration/deadline.
        # Predictions were computed at dispatch; SLA labels are audited
        # only after the independent simulator completes the task.
        predicted_finish = expected + timedelta(minutes=float(task.duration))
        predicted_met = predicted_finish <= task.sla_deadline
        actual_met = task.finish_time <= task.sla_deadline
        predicted_slack_min = (task.sla_deadline - predicted_finish).total_seconds()/60
        actual_slack_min = (task.sla_deadline - task.finish_time).total_seconds()/60
        errors.append(abs(error_minutes))
        detailed.append({
            "seed": seed,
            "policy": policy,
            "job_name": task.job_name,
            "origin_dc_id": task.origin_dc_id,
            "dest_dc_id": task.dest_dc_id,
            "is_remote": is_remote,
            "predicted_start_utc": expected.isoformat(),
            "actual_start_utc": actual.isoformat(),
            "residual_actual_minus_prediction_minutes": error_minutes,
            "abs_error_minutes": abs(error_minutes),
            "predicted_finish_utc": predicted_finish.isoformat(),
            "actual_finish_utc": task.finish_time.isoformat(),
            "deadline_utc": task.sla_deadline.isoformat(),
            "predicted_sla_met": predicted_met,
            "actual_sla_met": actual_met,
            "predicted_slack_minutes": predicted_slack_min,
            "actual_slack_minutes": actual_slack_min,
            "false_safe": predicted_met and not actual_met,
            "false_alarm": (not predicted_met) and actual_met,
        })
    if not detailed:
        return {
            "forecast_count": 0, "forecast_mae_minutes": None,
            "forecast_p95_abs_minutes": None,
            "forecast_bias_minutes": None,
            "forecast_overoptimistic_fraction": None,
            "forecast_local_mae_minutes": None,
            "forecast_remote_mae_minutes": None,
            "forecast_predicted_sla_misses": 0,
            "forecast_actual_sla_misses": 0,
            "forecast_false_safe_count": 0,
            "forecast_false_alarm_count": 0,
            "forecast_false_safe_fraction": None,
            "forecast_sla_confusion_counts": {
                "pred_met_actual_met": 0, "pred_met_actual_miss": 0,
                "pred_miss_actual_met": 0, "pred_miss_actual_miss": 0,
            },
        }, detailed
    sorted_abs = sorted(errors)
    remote_errors = [r["abs_error_minutes"] for r in detailed if r["is_remote"]]
    local_errors = [r["abs_error_minutes"] for r in detailed if not r["is_remote"]]
    return {
        "forecast_count": len(detailed),
        "forecast_mae_minutes": mean(sorted_abs),
        "forecast_p95_abs_minutes": sorted_abs[math.ceil(0.95 * len(sorted_abs))-1],
        "forecast_bias_minutes": mean(r["residual_actual_minus_prediction_minutes"] for r in detailed),
        "forecast_overoptimistic_fraction": mean(
            r["residual_actual_minus_prediction_minutes"] > 0 for r in detailed
        ),
        "forecast_local_mae_minutes": mean(local_errors) if local_errors else None,
        "forecast_remote_mae_minutes": mean(remote_errors) if remote_errors else None,
        "forecast_predicted_sla_misses": sum(not r["predicted_sla_met"] for r in detailed),
        "forecast_actual_sla_misses": sum(not r["actual_sla_met"] for r in detailed),
        "forecast_false_safe_count": sum(r["false_safe"] for r in detailed),
        "forecast_false_alarm_count": sum(r["false_alarm"] for r in detailed),
        "forecast_false_safe_fraction": mean(r["false_safe"] for r in detailed),
        "forecast_sla_confusion_counts": {
            "pred_met_actual_met": sum(r["predicted_sla_met"] and r["actual_sla_met"] for r in detailed),
            "pred_met_actual_miss": sum(r["false_safe"] for r in detailed),
            "pred_miss_actual_met": sum(r["false_alarm"] for r in detailed),
            "pred_miss_actual_miss": sum((not r["predicted_sla_met"]) and (not r["actual_sla_met"]) for r in detailed),
        },
    }, detailed
