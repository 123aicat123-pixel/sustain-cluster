"""Decision-time completion forecast audit for SustainCluster pilot.

Compare forecasts made at routing time with actual task finish times only
when the task is OBSERVED as completed by the simulator. An unfinished job
is explicitly censored; its finish_time attribute alone is not a completion.
All errors are in minutes. Positive bias means the forecast was too early.
"""
import math
from datetime import timedelta


def _mean(values):
    return sum(values) / len(values) if values else None


def _p90(values):
    if not values:
        return None
    return sorted(values)[math.ceil(0.9 * len(values)) - 1]


def summarize_forecasts(predictions, finished_tasks, buffer_minutes=30,
                        decision_buffers=None):
    """Return (metrics, rows) with complete and censored outcomes.

    predictions: mapping of task object -> predicted finish datetime or None,
        populated ONLY at the first committed routing decision for that task.
    finished_tasks: task objects from the simulator's completed-task reports.
    """
    if not math.isfinite(buffer_minutes) or buffer_minutes < 0:
        raise ValueError("Risk buffer must be nonnegative and finite")
    finished = set(finished_tasks)
    errors = []
    abs_errors = []
    false_safe = 0
    safe_predictions = 0
    buffer_failures = 0
    predicted = 0
    evaluated = 0
    no_prediction = 0
    unfinished = 0
    rows = []
    decision_evaluable = 0
    decision_failures = 0
    decision_safe_completed = 0
    decision_false_safe = 0
    for index, (task, prediction) in enumerate(predictions.items()):
        completed = task in finished
        actual = getattr(task, "finish_time", None) if completed else None
        deadline = task.sla_deadline
        if completed and actual is None:
            raise AssertionError("Completed task has no finish_time")
        error_min = None
        decision_margin = (
            decision_buffers.get(task) if decision_buffers is not None else None
        )
        if decision_margin is not None:
            if not math.isfinite(decision_margin) or decision_margin < 0:
                raise ValueError("Non-finite/negative decision margin")
        predicted_safe = None
        decision_predicted_safe = None
        actual_met = None if not completed else actual <= deadline
        if prediction is None:
            no_prediction += 1
        else:
            predicted += 1
            predicted_safe = prediction <= deadline
            if decision_margin is not None:
                decision_predicted_safe = (
                    prediction + timedelta(minutes=decision_margin)
                    <= deadline
                )
            if completed:
                evaluated += 1
                error_min = (actual - prediction).total_seconds() / 60
                if not math.isfinite(error_min):
                    raise AssertionError("Non-finite forecast error")
                errors.append(error_min)
                abs_errors.append(abs(error_min))
                buffer_failures += int(error_min > buffer_minutes)
                if decision_margin is not None:
                    decision_evaluable += 1
                    decision_failures += int(error_min > decision_margin)
                    if decision_predicted_safe:
                        decision_safe_completed += 1
                        decision_false_safe += int(not actual_met)
                if predicted_safe:
                    safe_predictions += 1
                    false_safe += int(not actual_met)
        if not completed:
            unfinished += 1
        rows.append({
            "forecast_id": index,
            "job_name": str(getattr(task, "job_name", index)),
            "predicted_finish": prediction.isoformat() if prediction is not None else None,
            "actual_finish": actual.isoformat() if actual is not None else None,
            "deadline": deadline.isoformat(),
            "completed": completed,
            "predicted_met_sla": predicted_safe,
            "actual_met_sla": actual_met,
            "error_minutes": error_min,
            "decision_margin_minutes": decision_margin,
            "decision_predicted_safe": decision_predicted_safe,
        })
    return {
        "forecast_records": len(predictions),
        "forecast_available": predicted,
        "forecast_unavailable": no_prediction,
        "forecast_completed_evaluable": evaluated,
        "forecast_censored_unfinished": unfinished,
        "forecast_signed_bias_minutes": _mean(errors),
        "forecast_mae_minutes": _mean(abs_errors),
        "forecast_p90_abs_error_minutes": _p90(abs_errors),
        "forecast_positive_bias_rate": _mean([int(x > 0) for x in errors]),
        "forecast_error_above_buffer": buffer_failures,
        "forecast_buffer_coverage": (
            1 - buffer_failures / evaluated if evaluated else None
        ),
        "forecast_predicted_safe_completed": safe_predictions,
        "forecast_false_safe_completed": false_safe,
        "forecast_false_safe_rate": (
            false_safe / safe_predictions if safe_predictions else None
        ),
        "forecast_risk_buffer_minutes": float(buffer_minutes),
        "decision_margin_completed_evaluable": decision_evaluable,
        "decision_margin_covered_completed": decision_evaluable - decision_failures,
        "decision_margin_coverage_completed": (
            1 - decision_failures / decision_evaluable
            if decision_evaluable else None
        ),
        "decision_margin_predicted_safe_completed": decision_safe_completed,
        "decision_margin_false_safe_completed": decision_false_safe,
        "decision_margin_false_safe_rate_completed": (
            decision_false_safe / decision_safe_completed
            if decision_safe_completed else None
        ),
    }, rows
