"""Heldout matched original greedy versus bounded joint batch assignment.

Original FIFO DC simulator and original queue-aware greedy policy remain
baseline; the joint planner uses fixed beam_width=4, chunk_size=8,
risk buffer=30min. Both are predefined before any later test results.
Every result records actual SLA including overdue unfinished, actual
facility+network carbon, exact finished task identities, and routing
changes. Never compare percentages if finished sets differ.
"""
import argparse
import csv
import json
from pathlib import Path
from research_sci.chronological_eval import ROOT,run_one
from research_sci.temporal_robustness import planned_folds
from research_sci.capacity_sensitivity import verify_scales


def compare_pair(greedy,batch):
    keys=(
        "seed","capacity_scale","test_window_start","test_admissions_end",
        "train_window_start","train_admissions_end",
        "test_tasks_admitted","test_admission_signature",
        "train_routing_signature","train_admission_signature",
        "pretest_train_completed","pretest_learned_buffer_minutes",
        "applied_frozen_buffer_minutes","queue_discipline",
        "forecast_queue_discipline",
    )
    for key in keys:
        if greedy[key]!=batch[key]:
            raise AssertionError("Paired condition changed: "+key)
    if (greedy["batch_planner"],batch["batch_planner"])!=("greedy","beam4"):
        raise AssertionError("Not the predeclared greedy/beam4 comparison")
    if batch["test_joint_batch_plans"]<=0:
        raise AssertionError("Joint planner never activated")
    for row in (greedy,batch):
        if row["test_sla_met"]+row["test_sla_violated"]!=row["test_tasks_finished"]:
            raise AssertionError("SLA task conservation")
        if row["test_unfinished"]+row["test_tasks_finished"]!=row["test_tasks_admitted"]:
            raise AssertionError("Lifecycle count violation")
    identical=(greedy["test_finished_work_signature"]
               ==batch["test_finished_work_signature"])
    delta=(
        batch["test_total_carbon_kg"]-greedy["test_total_carbon_kg"]
        if identical else None
    )
    return {
        "seed":greedy["seed"],"capacity_scale":greedy["capacity_scale"],
        "window_index":greedy["window_index"],
        "admitted":greedy["test_tasks_admitted"],
        "finished_greedy":greedy["test_tasks_finished"],
        "finished_joint":batch["test_tasks_finished"],
        "on_time_greedy":greedy["test_sla_met"],
        "on_time_joint":batch["test_sla_met"],
        "deadline_failures_greedy":greedy["test_deadline_failures_including_overdue"],
        "deadline_failures_joint":batch["test_deadline_failures_including_overdue"],
        "deadline_failure_delta":(
            batch["test_deadline_failures_including_overdue"]
            -greedy["test_deadline_failures_including_overdue"]
        ),
        "overdue_unfinished_greedy":greedy["test_unfinished_overdue"],
        "overdue_unfinished_joint":batch["test_unfinished_overdue"],
        "routing_changed":(
            greedy["test_routing_signature"]!=batch["test_routing_signature"]
        ),
        "identical_completed_work":identical,
        "carbon_kg_greedy_raw":greedy["test_total_carbon_kg"],
        "carbon_kg_joint_raw":batch["test_total_carbon_kg"],
        "carbon_delta_kg_if_identical_work":delta,
        "carbon_delta_pct_if_identical_work":(
            100*delta/greedy["test_total_carbon_kg"]
            if delta is not None else None
        ),
        "joint_batch_plans":batch["test_joint_batch_plans"],
        "joint_beam_expansions":batch["test_joint_beam_expansions"],
        "joint_chunks":batch["test_joint_chunks"],
    }


def run_study(seeds,scales,starts,output):
    if not seeds or len(set(seeds))!=len(seeds):
        raise ValueError("Require unique nonempty seeds")
    scales=verify_scales(scales)
    plan=planned_folds(test_starts=starts)
    result=[]
    for scale in scales:
        for window in plan["test_windows"]:
            for seed in seeds:
                pair={}
                for planner in ("greedy","beam4"):
                    row,_=run_one(
                        seed,"fixed_30",calibration_steps=16,
                        gap_steps=window["test_gap_steps"],
                        test_steps=16,drain_steps=96,
                        capacity_scale=scale,sim_duration_days=7,
                        heldout_batch_planner=planner,
                    )
                    row["window_index"]=window["index"]
                    pair[planner]=row
                comparison=compare_pair(pair["greedy"],pair["beam4"])
                result.append(comparison)
                print(json.dumps({"phase":"JOINT_BATCH_PAIR",**comparison},
                                 allow_nan=False),flush=True)
    output=Path(output)
    output.parent.mkdir(exist_ok=True,parents=True)
    record={
        "protocol":"predeclared_greedy_vs_bounded_joint_batch_4x8",
        "seeds":list(seeds),"capacity_scales":list(scales),
        "windows":plan,"pairs":result,
        "warnings":(
            "Exploratory synthetic pressure settings, same underlying trace. "
            "Beam search is truncated at 4 states and 8 tasks per chunk; "
            "not a true globally optimal or trained RL algorithm. "
            "No future arrivals or true job emissions in routing objective. "
            "Percent CO2 differences suppressed if completed job sets differ. "
            "Result does not establish formal chance-constraint coverage."
        )
    }
    output.write_text(json.dumps(record,indent=2,allow_nan=False),encoding="utf-8")
    with output.with_suffix(".csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    return record


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seeds",nargs="+",type=int,default=[1,42])
    p.add_argument("--capacity-scales",nargs="+",type=float,default=[.02,.1])
    p.add_argument("--test-start-ticks",nargs="+",type=int,default=[288,448])
    p.add_argument("--output",type=Path,
        default=ROOT/"research_sci/results/joint_batch_study.json")
    args=p.parse_args()
    run_study(args.seeds,args.capacity_scales,tuple(args.test_start_ticks),
              args.output)


if __name__=="__main__":
    main()
