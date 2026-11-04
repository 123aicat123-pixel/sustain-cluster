"""State-risk diagnostic on later heldout windows, no new policy training.

Runs a common fixed_30 baseline over predeclared synthetic capacities and
later chronological windows. This tests whether observable dispatch-time
queue pressure is ASSOCIATED with subsequent optimistic prediction errors.
No test-data-driven feature selection, regression, or risk guarantee.
"""
import argparse
import csv
import json
from pathlib import Path

from research_sci.chronological_eval import ROOT, run_one
from research_sci.temporal_robustness import planned_folds
from research_sci.capacity_sensitivity import verify_scales


def analyze_pressure(results):
    if not results:
        raise ValueError("No observations")
    summary=[]
    for r in results:
        counts=r["test_state_risk_total"]
        strata=r["test_state_risk_by_pressure"]
        if counts["dispatches"] != r["test_tasks_admitted"]:
            raise AssertionError("Audit/admitted task count mismatch")
        if counts["completed"] != r["test_tasks_finished"]:
            raise AssertionError("Audit/completed task count mismatch")
        if counts["censored_unfinished"] != r["test_unfinished"]:
            raise AssertionError("Censoring mismatch")
        for name,groups in strata.items():
            if sum(g["dispatches"] for g in groups.values()) != r["test_tasks_admitted"]:
                raise AssertionError("Missing task pressure stratum")
        summary.append({
            "seed":r["seed"],
            "capacity_scale":r["capacity_scale"],
            "window_index":r["window_index"],
            "test_tasks_admitted":r["test_tasks_admitted"],
            "test_tasks_finished":r["test_tasks_finished"],
            "test_deadline_failures_including_overdue":r["test_deadline_failures_including_overdue"],
            "forecast_evaluable":counts["forecast_evaluable"],
            "censored_unfinished":counts["censored_unfinished"],
            "forecast_mae_minutes":counts["forecast_mae_minutes"],
            "forecast_signed_optimism_minutes":counts["forecast_signed_optimism_minutes"],
            "forecast_p90_absolute_error_minutes":counts["forecast_p90_absolute_error_minutes"],
            "pressure":strata,
        })
    return {
        "scope":"observational_predecision_state_vs_postcompletion_error",
        "experiment_rows":len(results),
        "per_seed_capacity_window":summary,
        "limitations":(
            "Predeclared bins are descriptive, not fitted predictors. "
            "Completed-only errors are censored/selection-biased. "
            "Replays omit intervening jobs and are not production-continuous. "
            "Shared seeds, one workload source, synthetic capacity, no causal "
            "inference, no formal SLA probability guarantee."
        )
    }


def run_study(seeds,scales,starts,output):
    if not seeds or len(seeds)!=len(set(seeds)):
        raise ValueError("Unique seeds required")
    scales=verify_scales(scales)
    plan=planned_folds(test_starts=starts)
    rows=[]
    directory=Path(output).with_name(Path(output).stem+"_per_task")
    for scale in scales:
        for window in plan["test_windows"]:
            for seed in seeds:
                row,_=run_one(
                    seed,"fixed_30",calibration_steps=16,
                    gap_steps=window["test_gap_steps"],
                    test_steps=16,drain_steps=96,capacity_scale=scale,
                    sim_duration_days=7,audit_states=True,
                    state_audit_dir=directory
                )
                row["window_index"]=window["index"]
                rows.append(row)
                stat=row["test_state_risk_total"]
                print(json.dumps({
                    "phase":"STATE_PRESSURE_AUDIT",
                    "seed":seed,"capacity":scale,"window":window["index"],
                    "admitted":row["test_tasks_admitted"],
                    "finished":row["test_tasks_finished"],
                    "censored":stat["censored_unfinished"],
                    "mae_min":stat["forecast_mae_minutes"],
                    "optimism_min":stat["forecast_signed_optimism_minutes"],
                    "p90_abs_min":stat["forecast_p90_absolute_error_minutes"],
                    "sla_deadline_failures":row["test_deadline_failures_including_overdue"],
                    "cpu_strata":row["test_state_risk_by_pressure"]["cpu_utilization"],
                    "queue_strata":row["test_state_risk_by_pressure"]["pending_queue"],
                    "inbound_strata":row["test_state_risk_by_pressure"]["committed_inbound"]
                },allow_nan=False),flush=True)
    evidence=analyze_pressure(rows)
    path=Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(evidence,indent=2,allow_nan=False),encoding="utf-8")
    with path.with_suffix(".csv").open("w",newline="",encoding="utf-8") as f:
        summary=evidence["per_seed_capacity_window"]
        fieldnames=list(dict.fromkeys(
            key for row in summary for key in row if key!="pressure"
        ))
        writer=csv.DictWriter(f,fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key:row[key] for key in fieldnames} for row in summary)
    return evidence


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seeds",nargs="+",type=int,default=[1,42])
    p.add_argument("--capacity-scales",nargs="+",type=float,default=[.02,.1])
    p.add_argument("--test-start-ticks",nargs="+",type=int,default=[288,448])
    p.add_argument("--output",type=Path,default=ROOT/"research_sci/results/state_risk_study.json")
    args=p.parse_args()
    run_study(args.seeds,args.capacity_scales,tuple(args.test_start_ticks),args.output)


if __name__=="__main__":
    main()
