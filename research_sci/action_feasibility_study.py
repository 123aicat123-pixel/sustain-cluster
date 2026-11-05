"""Audited opportunity analysis: one-task hypothetical choices at all centers.

A read-only comparison of predecision SLA-feasible candidates with the
actually selected route. This is NOT a causal estimate: changing routes
would change later queue states, carbon and completion outcomes.
"""
import argparse
import json
from pathlib import Path

from research_sci.chronological_eval import ROOT, run_one
from research_sci.temporal_robustness import planned_folds
from research_sci.capacity_sensitivity import verify_scales


def summarize(rows):
    if not rows:
        raise ValueError("No rows")
    output=[]
    for row in rows:
        audit=row["test_action_feasibility"]
        if audit["dispatches"] != row["test_tasks_admitted"]:
            raise AssertionError("All admitted jobs require candidate snapshots")
        if audit["completed"] != row["test_tasks_finished"]:
            raise AssertionError("Observed completed task count mismatch")
        if audit["censored_unfinished"] != row["test_unfinished"]:
            raise AssertionError("Unfinished tasks must not become false negatives")
        if audit["observed_sla_misses_completed"] != row["test_sla_violated"]:
            raise AssertionError("Observed completed misses mismatch")
        if audit["no_unbuffered_feasible_center"] > audit["dispatches"]:
            raise AssertionError("Invalid feasible-set count")
        if audit["unbuffered_predicted_rescue_elsewhere"] > audit["dispatches"]:
            raise AssertionError("Invalid predicted alternatives")
        output.append({
            "seed":row["seed"],"capacity_scale":row["capacity_scale"],
            "window_index":row["window_index"],
            "admitted":audit["dispatches"],
            "completed":audit["completed"],
            "censored":audit["censored_unfinished"],
            "real_sla_failures_with_overdue":row["test_deadline_failures_including_overdue"],
            "chosen_predicted_late":audit["chosen_unbuffered_predicted_late"],
            "no_candidate_forecast":audit["no_candidate_forecast"],
            "no_optimistically_feasible_center":audit["no_unbuffered_feasible_center"],
            "no_buffered_feasible_center":audit["no_buffered_feasible_center"],
            "predicted_alternative_while_chosen_late":
                audit["unbuffered_predicted_rescue_elsewhere"],
            "observed_miss_with_predicted_alternative":
                audit["unbuffered_predicted_rescue_and_actual_missed_completed"],
            "buffered_predicted_alternative":
                audit["buffered_predicted_rescue_elsewhere"],
            "lowest_intensity_buffered_feasible_selection_fraction":
                audit["buffered_cheapest_intensity_selection_fraction_if_defined"],
        })
    return {
        "scope":"predecision_all_datacenters_one_task_hypothetical_forecasts",
        "runs":len(rows),"per_seed_capacity_window":output,
        "disclaimer":(
            "Predicted feasible alternatives are NOT proven SLA rescues. "
            "Choosing an alternative would alter future congestion. "
            "Instantaneous grid intensity is not incremental job CO2. "
            "All outcomes are from the actually chosen route only."
        )
    }


def run_study(seeds,scales,test_starts,output):
    if not seeds or len(set(seeds))!=len(seeds):
        raise ValueError("Unique nonempty seeds required")
    scales=verify_scales(scales)
    plan=planned_folds(test_starts=test_starts)
    per_task_dir=Path(output).with_name(Path(output).stem+"_per_task")
    rows=[]
    for scale in scales:
        for window in plan["test_windows"]:
            for seed in seeds:
                row,_=run_one(
                    seed,"fixed_30",calibration_steps=16,
                    gap_steps=window["test_gap_steps"],
                    test_steps=16,drain_steps=96,capacity_scale=scale,
                    sim_duration_days=7,audit_candidates=True,
                    candidate_audit_dir=per_task_dir
                )
                row["window_index"]=window["index"]
                rows.append(row)
                audit=row["test_action_feasibility"]
                print(json.dumps({
                    "phase":"CANDIDATE_FEASIBILITY_AUDIT",
                    "seed":seed,"capacity":scale,"window":window["index"],
                    "admitted":audit["dispatches"],
                    "completed":audit["completed"],
                    "censored":audit["censored_unfinished"],
                    "actual_sla_misses":row["test_deadline_failures_including_overdue"],
                    "no_candidate_forecast":audit["no_candidate_forecast"],
                    "no_optimistic_feasible_center":audit["no_unbuffered_feasible_center"],
                    "no_buffered_feasible_center":audit["no_buffered_feasible_center"],
                    "chosen_predicted_late":audit["chosen_unbuffered_predicted_late"],
                    "predicted_rescue_elsewhere":
                        audit["unbuffered_predicted_rescue_elsewhere"],
                    "observed_miss_with_predicted_rescue":
                        audit["unbuffered_predicted_rescue_and_actual_missed_completed"],
                    "buffered_cheapest_intensity_fraction":
                        audit["buffered_cheapest_intensity_selection_fraction_if_defined"],
                },allow_nan=False),flush=True)
    evidence=summarize(rows)
    destination=Path(output)
    destination.parent.mkdir(exist_ok=True,parents=True)
    destination.write_text(json.dumps(evidence,indent=2,allow_nan=False),
                           encoding="utf-8")
    return evidence


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--seeds",nargs="+",type=int,default=[1,42])
    parser.add_argument("--capacity-scales",nargs="+",type=float,default=[.02,.1])
    parser.add_argument("--test-start-ticks",nargs="+",type=int,default=[288,448])
    parser.add_argument("--output",type=Path,
        default=ROOT/"research_sci/results/action_feasibility_study.json")
    args=parser.parse_args()
    run_study(args.seeds,args.capacity_scales,tuple(args.test_start_ticks),
              args.output)


if __name__=="__main__":
    main()
