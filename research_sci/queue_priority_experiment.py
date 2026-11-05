"""Matched, held-out FIFO vs EDF queue-discipline experiment.

The queue discipline and its completion-time estimator are both changed.
The earlier calibration cohort stays FIFO in both treatments. The variants
are fixed BEFORE heldout evaluation; no parameter or policy is chosen
from test performance. Replays share the same chronological task arrivals.
Results from different completed-work sets cannot be compared on CO2.
"""
import argparse
import csv
import json
from pathlib import Path

from research_sci.chronological_eval import ROOT, run_one
from research_sci.temporal_robustness import planned_folds
from research_sci.capacity_sensitivity import verify_scales


def pair_report(fifo, edf):
    for field in (
        "seed", "capacity_scale", "train_window_start", "train_admissions_end",
        "test_window_start", "test_admissions_end",
        "test_tasks_admitted", "test_admission_signature",
        "train_routing_signature", "train_admission_signature",
        "pretest_train_completed", "pretest_learned_buffer_minutes",
        "applied_frozen_buffer_minutes",
    ):
        if fifo[field] != edf[field]:
            raise AssertionError("Unmatched paired conditions: "+field)
    if fifo["queue_discipline"] != "fifo" or edf["queue_discipline"] != "edf":
        raise AssertionError("Queue execution configuration differs from intended")
    if fifo["test_sla_met"]+fifo["test_sla_violated"]!=fifo["test_tasks_finished"]:
        raise AssertionError("FIFO SLA outcomes not conserved")
    if edf["test_sla_met"]+edf["test_sla_violated"]!=edf["test_tasks_finished"]:
        raise AssertionError("EDF SLA outcomes not conserved")
    same_completed=(
        fifo["test_finished_work_signature"]
        ==edf["test_finished_work_signature"]
    )
    carbon_delta=(
        edf["test_total_carbon_kg"]-fifo["test_total_carbon_kg"]
        if same_completed else None
    )
    return {
        "seed":fifo["seed"],"capacity_scale":fifo["capacity_scale"],
        "window_index":fifo["window_index"],
        "test_tasks_admitted":fifo["test_tasks_admitted"],
        "finished_fifo":fifo["test_tasks_finished"],
        "finished_edf":edf["test_tasks_finished"],
        "same_completed_work_set":same_completed,
        "completed_core_minutes_fifo":fifo["test_completed_core_minutes"],
        "completed_core_minutes_edf":edf["test_completed_core_minutes"],
        "actual_sla_failures_fifo":fifo["test_deadline_failures_including_overdue"],
        "actual_sla_failures_edf":edf["test_deadline_failures_including_overdue"],
        "sla_failure_delta_edf_minus_fifo":(
            edf["test_deadline_failures_including_overdue"]
            -fifo["test_deadline_failures_including_overdue"]
        ),
        "unfinished_fifo":fifo["test_unfinished"],
        "unfinished_edf":edf["test_unfinished"],
        "overdue_unfinished_fifo":fifo["test_unfinished_overdue"],
        "overdue_unfinished_edf":edf["test_unfinished_overdue"],
        "carbon_kg_fifo_raw":fifo["test_total_carbon_kg"],
        "carbon_kg_edf_raw":edf["test_total_carbon_kg"],
        "carbon_difference_kg_if_same_work":carbon_delta,
        "carbon_difference_pct_if_same_work": (
            100*carbon_delta/fifo["test_total_carbon_kg"]
            if carbon_delta is not None else None
        ),
        "routing_signature_changed":(
            fifo["test_routing_signature"]!=edf["test_routing_signature"]
        ),
    }


def run_experiment(seeds, scales, starts, output):
    if not seeds or len(set(seeds))!=len(seeds):
        raise ValueError("Require unique seeds")
    scales=verify_scales(scales)
    plan=planned_folds(test_starts=starts)
    records=[]
    for scale in scales:
        for window in plan["test_windows"]:
            for seed in seeds:
                pair={}
                for queue_order in ("fifo","edf"):
                    row,_=run_one(
                        seed,"fixed_30",calibration_steps=16,
                        gap_steps=window["test_gap_steps"],
                        test_steps=16,drain_steps=96,
                        capacity_scale=scale,sim_duration_days=7,
                        heldout_queue_order=queue_order,
                    )
                    row["window_index"]=window["index"]
                    pair[queue_order]=row
                entry=pair_report(pair["fifo"],pair["edf"])
                records.append(entry)
                print(json.dumps({"phase":"QUEUE_PRIORITY_PAIR",**entry},
                                 allow_nan=False),flush=True)
    result={
        "design":"predeclared_fifo_vs_edf_queue_and_matching_predictor",
        "seeds":list(seeds),"scales":list(scales),
        "windows":plan,"per_seed_pairs":records,
        "same_completed_work_pairs":sum(
            int(r["same_completed_work_set"]) for r in records
        ),
        "warning":(
            "EDF is a standard baseline. Joint queue-order and route-forecast "
            "intervention; independent test replays not production continuity. "
            "Actual future queue trajectories differ by design. Per-pair "
            "carbon differences omitted if completed work sets differ. "
            "No test-set parameter tuning or statistical generalization claim."
        ),
    }
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,allow_nan=False),
                      encoding="utf-8")
    with output.with_suffix(".csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seeds",nargs="+",type=int,default=[1,42])
    p.add_argument("--capacity-scales",nargs="+",type=float,default=[.02,.1])
    p.add_argument("--test-start-ticks",nargs="+",type=int,default=[288,448])
    p.add_argument("--output",type=Path,
        default=ROOT/"research_sci/results/queue_priority.json")
    args=p.parse_args()
    run_experiment(args.seeds,args.capacity_scales,
                   tuple(args.test_start_ticks),args.output)


if __name__=="__main__":
    main()
