"""All-datacenter pre-dispatch queue-feasibility *audit*, not an optimizer.

Every candidate is evaluated from exactly the same observed clock,
running/pending queues and known in-transit/earlier-batch commitments as
the real scheduling decision. Future jobs, actual finishes of pending
jobs, hidden future carbon, counterfactual outcomes are NEVER accessed.

Alternative predictions are hypothetical *one-task* placements assuming
all prior commitments remain unchanged. They do not model later
decisions or prove actual SLA rescue. Current carbon intensity is only
a GRID INTENSITY PROXY, not measured marginal CO2 of routing there.
"""
import math

from research_sci.queue_risk import predict_finish


def evaluate_candidates(task, datacenters, now, cluster_manager,
                        known_arrivals_by_dc, chosen_dc_id,
                        step_seconds=900, buffer_minutes=30.0,
                        delay_fn=None, forced_origin=False):
    if not isinstance(step_seconds, int) or step_seconds <= 0:
        raise ValueError("step_seconds must be a positive integer")
    if not math.isfinite(buffer_minutes) or buffer_minutes < 0:
        raise ValueError("Buffer must be finite and nonnegative")
    if delay_fn is None:
        from data.network_cost.network_delay import get_transmission_delay
        delay_fn = get_transmission_delay
    centers = sorted(datacenters.values(), key=lambda dc: dc.dc_id)
    if not centers:
        raise ValueError("No datacenters")
    if len(set(dc.dc_id for dc in centers)) != len(centers):
        raise ValueError("Duplicate datacenter IDs")
    if chosen_dc_id not in {dc.dc_id for dc in centers}:
        raise ValueError("Chosen DC not found")
    origin = cluster_manager.get_dc_location(task.origin_dc_id)
    candidates = []
    for dc in centers:
        current_commitments = list(known_arrivals_by_dc.get(dc.dc_id, ()))
        if any(earlier is task for _, earlier in current_commitments):
            raise AssertionError("Target job already committed at decision")
        delay = float(delay_fn(
            origin, dc.location, cluster_manager.cloud_provider,
            task.bandwidth_gb
        ))
        carbon = float(dc.get_current_carbon_intensity(norm=False))
        if not math.isfinite(delay) or delay < 0:
            raise ValueError("Invalid network delay")
        if not math.isfinite(carbon) or carbon < 0:
            raise ValueError("Invalid observed carbon intensity")
        arrival_ticks = max(1, math.ceil(delay / step_seconds))
        forecast = predict_finish(
            task, dc, now, arrival_ticks, step_seconds=step_seconds,
            known_arrivals=current_commitments
        )
        slack = (
            (task.sla_deadline - forecast).total_seconds() / 60
            if forecast is not None else None
        )
        candidates.append({
            "dc_id":int(dc.dc_id),
            "network_delay_seconds":delay,
            "arrival_ticks":arrival_ticks,
            "forecast_finish":forecast.isoformat() if forecast is not None else None,
            "forecast_slack_minutes":slack,
            "forecast_unbuffered_sla_feasible":(
                slack is not None and slack >= 0
            ),
            "forecast_buffered_sla_feasible":(
                slack is not None and slack >= buffer_minutes
            ),
            "observed_carbon_intensity":carbon,
            "currently_has_resources":bool(dc.can_schedule(task)),
            "known_inbound":len(current_commitments),
            "pending_count":len(dc.pending_tasks),
        })
    chosen=next(x for x in candidates if x["dc_id"] == chosen_dc_id)
    feasible0=[x for x in candidates if x["forecast_unbuffered_sla_feasible"]]
    feasibleb=[x for x in candidates if x["forecast_buffered_sla_feasible"]]
    forecastable=[x for x in candidates if x["forecast_finish"] is not None]
    earlier=min(forecastable, key=lambda x: (
        x["forecast_finish"],x["observed_carbon_intensity"],x["dc_id"]
    )) if forecastable else None
    cheapest0=min(feasible0,key=lambda x: (
        x["observed_carbon_intensity"],x["forecast_finish"],x["dc_id"]
    )) if feasible0 else None
    cheapestb=min(feasibleb,key=lambda x: (
        x["observed_carbon_intensity"],x["forecast_finish"],x["dc_id"]
    )) if feasibleb else None
    # Relative carbon *intensity* is descriptive and not per-job emissions.
    return {
        "task_name":str(task.job_name),
        "decision_time":now.isoformat(),
        "selected_dc_id":int(chosen_dc_id),
        "forced_origin":bool(forced_origin),
        "buffer_minutes":float(buffer_minutes),
        "total_dc_count":len(candidates),
        "forecastable_count":len(forecastable),
        "unbuffered_feasible_count":len(feasible0),
        "buffered_feasible_count":len(feasibleb),
        "selected_forecast_finish":chosen["forecast_finish"],
        "selected_forecast_slack_minutes":chosen["forecast_slack_minutes"],
        "selected_forecast_unbuffered_feasible":chosen["forecast_unbuffered_sla_feasible"],
        "selected_forecast_buffered_feasible":chosen["forecast_buffered_sla_feasible"],
        "any_unbuffered_feasible":bool(feasible0),
        "any_buffered_feasible":bool(feasibleb),
        "forecastable_but_none_feasible":bool(forecastable) and not bool(feasible0),
        "predicted_unbuffered_rescue_elsewhere":(
            not chosen["forecast_unbuffered_sla_feasible"] and bool(feasible0)
        ),
        "predicted_buffered_rescue_elsewhere":(
            not chosen["forecast_buffered_sla_feasible"] and bool(feasibleb)
        ),
        "min_predicted_finish_dc_id":earlier["dc_id"] if earlier else None,
        "lowest_intensity_feasible_dc_id":cheapest0["dc_id"] if cheapest0 else None,
        "lowest_intensity_buffered_feasible_dc_id":(
            cheapestb["dc_id"] if cheapestb else None
        ),
        "selected_intensity_is_cheapest_feasible":(
            chosen_dc_id == cheapest0["dc_id"] if cheapest0 else None
        ),
        "selected_intensity_is_cheapest_buffered_feasible":(
            chosen_dc_id == cheapestb["dc_id"] if cheapestb else None
        ),
        "selected_observed_carbon_intensity":chosen["observed_carbon_intensity"],
        "candidate_centers":candidates,
    }


def summarize_candidate_audit(decisions, finished_tasks):
    """Join actual outcomes only AFTER simulator horizon, preserving censoring."""
    finished=set(finished_tasks)
    if not decisions:
        raise ValueError("Empty candidate audit")
    summary={
        "dispatches":len(decisions),
        "completed":0,
        "censored_unfinished":0,
        "no_candidate_forecast":0,
        "no_unbuffered_feasible_center":0,
        "no_buffered_feasible_center":0,
        "chosen_unbuffered_predicted_late":0,
        "chosen_buffered_predicted_late":0,
        "unbuffered_predicted_rescue_elsewhere":0,
        "buffered_predicted_rescue_elsewhere":0,
        "observed_sla_misses_completed":0,
        "predicted_late_selected_and_actual_missed_completed":0,
        "unbuffered_predicted_rescue_and_actual_missed_completed":0,
        "lowest_intensity_buffered_feasible_count":0,
        "chosen_is_lowest_intensity_buffered_feasible_count":0,
    }
    rows=[]
    for task,decision in decisions.items():
        if decision["forecastable_count"] == 0:
            summary["no_candidate_forecast"]+=1
        if not decision["any_unbuffered_feasible"]:
            summary["no_unbuffered_feasible_center"]+=1
        if not decision["any_buffered_feasible"]:
            summary["no_buffered_feasible_center"]+=1
        if not decision["selected_forecast_unbuffered_feasible"]:
            summary["chosen_unbuffered_predicted_late"]+=1
        if not decision["selected_forecast_buffered_feasible"]:
            summary["chosen_buffered_predicted_late"]+=1
        if decision["predicted_unbuffered_rescue_elsewhere"]:
            summary["unbuffered_predicted_rescue_elsewhere"]+=1
        if decision["predicted_buffered_rescue_elsewhere"]:
            summary["buffered_predicted_rescue_elsewhere"]+=1
        if decision["any_buffered_feasible"]:
            summary["lowest_intensity_buffered_feasible_count"]+=1
            summary["chosen_is_lowest_intensity_buffered_feasible_count"]+=int(
                decision["selected_intensity_is_cheapest_buffered_feasible"]
            )
        completed=task in finished
        actual=getattr(task,"finish_time",None) if completed else None
        if completed and actual is None:
            raise AssertionError("Completed task missing actual finish")
        actual_met=(actual <= task.sla_deadline) if completed else None
        summary["completed"]+=int(completed)
        summary["censored_unfinished"]+=int(not completed)
        if completed and not actual_met:
            summary["observed_sla_misses_completed"]+=1
            if not decision["selected_forecast_unbuffered_feasible"]:
                summary["predicted_late_selected_and_actual_missed_completed"]+=1
            if decision["predicted_unbuffered_rescue_elsewhere"]:
                summary["unbuffered_predicted_rescue_and_actual_missed_completed"]+=1
        rows.append({
            **decision,
            "completed":completed,
            "actual_met_sla":actual_met,
            "actual_finish":actual.isoformat() if actual is not None else None,
        })
    if summary["completed"]+summary["censored_unfinished"]!=summary["dispatches"]:
        raise AssertionError("Lifecycle audit missing tasks")
    summary["fraction_without_optimistic_feasible_center"]=(
        summary["no_unbuffered_feasible_center"]/summary["dispatches"]
    )
    summary["fraction_without_buffered_feasible_center"]=(
        summary["no_buffered_feasible_center"]/summary["dispatches"]
    )
    summary["fraction_with_predicted_rescue_alternative"]=(
        summary["unbuffered_predicted_rescue_elsewhere"]/summary["dispatches"]
    )
    summary["buffered_cheapest_intensity_selection_fraction_if_defined"]=(
        summary["chosen_is_lowest_intensity_buffered_feasible_count"]/
        summary["lowest_intensity_buffered_feasible_count"]
        if summary["lowest_intensity_buffered_feasible_count"] else None
    )
    summary["limitations"]=(
        "Counterfactual one-task queue predictions are not real outcomes or "
        "proof of avoidable SLA misses. Candidate carbon *grid intensity* "
        "is not measured incremental emissions. Completion labels are "
        "censored for unfinished tasks. No causal effect claim."
    )
    return summary,rows
