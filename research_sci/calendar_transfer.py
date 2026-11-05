"""Locked September/October workload transfer of three routing methods.

August outcomes motivated a fixed hypothesis: use joint beam search
only when >=50% of currently visible jobs have at least one predicted
unbuffered SLA-feasible datacenter. The gate never reads future jobs or
test outcomes. This transfers to truly later workload DATE slices, not
merely other hours of August, using the same Alibaba-2020 data source.

All methods are PREDECLARED: greedy, beam4 and gate50. No margin,
beam width, chunk size or gate threshold is reselected using these
months. Experiment is exploratory and 2 seeds per calendar month
are not independent datasets or enough for inferential statistics.
"""
import argparse
import csv
import json
from pathlib import Path

from research_sci.chronological_eval import ROOT,run_one
from research_sci.temporal_robustness import planned_folds
from research_sci.capacity_sensitivity import verify_scales

METHODS=("greedy","beam4","gate50")


def audit_transfer(rows):
    pairs={(r["batch_planner"]):r for r in rows}
    if set(pairs)!=set(METHODS) or len(rows)!=len(METHODS):
        raise AssertionError("Incomplete three-policy transfer comparison")
    reference=pairs["greedy"]
    for row in rows:
        for field in (
            "seed","capacity_scale","calendar_month","calendar_day",
            "test_window_start","test_admissions_end",
            "train_window_start","train_admissions_end",
            "test_tasks_admitted","test_admission_signature",
            "train_routing_signature","train_admission_signature",
            "pretest_train_completed","pretest_learned_buffer_minutes",
            "applied_frozen_buffer_minutes","queue_discipline",
            "forecast_queue_discipline"
        ):
            if reference[field]!=row[field]:
                raise AssertionError("Transfer conditions differ: "+field)
        if row["test_sla_met"]+row["test_sla_violated"]!=row["test_tasks_finished"]:
            raise AssertionError("SLA completed-task conservation")
        if row["test_tasks_finished"]+row["test_unfinished"]!=row["test_tasks_admitted"]:
            raise AssertionError("Unfinished-task conservation")
    out=[]
    for method in METHODS:
        row=pairs[method]
        identical=(
            reference["test_finished_work_signature"]
            ==row["test_finished_work_signature"]
        )
        co2_change=(
            100*(row["test_total_carbon_kg"]/
                 reference["test_total_carbon_kg"]-1)
            if identical else None
        )
        out.append({
            "method":method,
            "calendar_month":row["calendar_month"],
            "calendar_day":row["calendar_day"],
            "seed":row["seed"],
            "capacity_scale":row["capacity_scale"],
            "window_index":row["window_index"],
            "admitted":row["test_tasks_admitted"],
            "finished":row["test_tasks_finished"],
            "on_time":row["test_sla_met"],
            "actual_sla_failure_including_overdue":
                row["test_deadline_failures_including_overdue"],
            "sla_delta_vs_greedy":(
                row["test_deadline_failures_including_overdue"]
                -reference["test_deadline_failures_including_overdue"]
            ),
            "overdue_unfinished":row["test_unfinished_overdue"],
            "same_completed_work_as_greedy":identical,
            "total_carbon_kg_raw":row["test_total_carbon_kg"],
            "carbon_change_pct_if_identical_work":co2_change,
            "routing_signature_changed":(
                row["test_routing_signature"]
                !=reference["test_routing_signature"]
            ),
            "gate_batches":row["test_gate_batches"],
            "gate_activated_batches":row["test_gate_activated_batches"],
            "gate_tasks":row["test_gate_tasks"],
            "gate_feasible_tasks":row["test_gate_feasible_tasks"],
            "joint_batch_plans":row["test_joint_batch_plans"],
        })
    return out


def run_transfer(month,day,seeds,scales,starts,output):
    if (month,day) not in ((9,1),(10,1)):
        raise ValueError("Only preregistered calendar periods Sep 1 / Oct 1")
    if not seeds or len(set(seeds))!=len(seeds):
        raise ValueError("Require unique seeds")
    scales=verify_scales(scales)
    plan=planned_folds(test_starts=starts)
    result=[]
    for scale in scales:
        for window in plan["test_windows"]:
            for seed in seeds:
                group=[]
                for method in METHODS:
                    row,_=run_one(
                        seed,"fixed_30",calibration_steps=16,
                        gap_steps=window["test_gap_steps"],
                        test_steps=16,drain_steps=96,
                        capacity_scale=scale,sim_duration_days=7,
                        calendar_month=month,calendar_day=day,
                        heldout_batch_planner=method
                    )
                    if row["calendar_month"]!=month or row["calendar_day"]!=day:
                        raise AssertionError("Calendar workload period not honored")
                    row["window_index"]=window["index"]
                    group.append(row)
                for item in audit_transfer(group):
                    result.append(item)
                    print(json.dumps({"phase":"NEW_CALENDAR_TRANSFER",**item},
                                     allow_nan=False),flush=True)
    output=Path(output)
    output.parent.mkdir(exist_ok=True,parents=True)
    report={
        "protocol":"September_October_independent_calendar_transfer_fixed_gate50",
        "new_calendar_start":f"2023-{month:02d}-{day:02d}T05:00:00+00:00",
        "workload_mapped_year":2020,
        "methods":list(METHODS),"seeds":list(seeds),"scales":list(scales),
        "windows":plan,"results":result,
        "fixed_prior_settings":{
            "margin_minutes":30,"beam_width":4,"chunk_size":8,
            "gate_threshold":0.5,"minimum_batch_size":2,
        },
        "limitations":(
            "Threshold was hypothesized after inspecting August exploratory "
            "results; September/October are new calendar workload slices "
            "within SAME Alibaba dataset, NOT distinct workloads. "
            "No hyperparameter selection after test and no multiple-testing "
            "adjustment. Finished task identities are compared before "
            "descriptive CO2 claims. Fixed 7-day simulator, gapped cohort "
            "replays and two seeds are not enough for SCI generalization."
        )
    }
    output.write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    with output.with_suffix(".csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--month",type=int,required=True)
    p.add_argument("--day",type=int,default=1)
    p.add_argument("--seeds",nargs="+",type=int,default=[1,42])
    p.add_argument("--capacity-scales",nargs="+",type=float,default=[.02,.1])
    p.add_argument("--test-start-ticks",nargs="+",type=int,default=[288,448])
    p.add_argument("--output",type=Path,
                   default=ROOT/"research_sci/results/calendar_transfer.json")
    args=p.parse_args()
    run_transfer(args.month,args.day,args.seeds,args.capacity_scales,
                 tuple(args.test_start_ticks),args.output)


if __name__=="__main__":
    main()
