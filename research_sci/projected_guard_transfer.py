"""Predeclared November/December shadow-guard transfer on new workloads.

The fixed algorithms and risk tolerances were specified after observing
August/September/October pilot behavior. These future calendar periods
therefore provide later, not previously inspected date slices of the
SAME Alibaba workload, not an independent dataset. No model is trained.
All policy arms are re-simulated with identical arrivals, seeds,
original FIFO execution, synthetic capacities and completed work checks.
"""
import argparse
import csv
import json
from pathlib import Path

from research_sci.chronological_eval import ROOT,run_one
from research_sci.temporal_robustness import planned_folds
from research_sci.capacity_sensitivity import verify_scales

METHODS=("greedy","beam4","guard0","guard15")


def evaluate_group(rows):
    by={r["batch_planner"]:r for r in rows}
    if set(by)!=set(METHODS) or len(rows)!=len(METHODS):
        raise AssertionError("Missing or duplicate predeclared guard arm")
    base=by["greedy"]
    keys=(
        "seed","capacity_scale","calendar_month","calendar_day",
        "test_window_start","test_admissions_end",
        "train_window_start","train_admissions_end",
        "test_tasks_admitted","test_admission_signature",
        "train_routing_signature","train_admission_signature",
        "pretest_train_completed","pretest_train_forecast_residuals",
        "applied_frozen_buffer_minutes","fixed_policy_without_calibration",
        "queue_discipline","forecast_queue_discipline"
    )
    for r in rows:
        for key in keys:
            if r[key]!=base[key]:
                raise AssertionError("Unmatched guard transfer: "+key)
        if r["pretest_train_completed"] or r["pretest_train_forecast_residuals"]:
            raise AssertionError("Fixed transfer must not fit local training data")
        if not r["fixed_policy_without_calibration"]:
            raise AssertionError("Fixed-policy test admitted training tasks")
        if r["test_sla_met"]+r["test_sla_violated"]!=r["test_tasks_finished"]:
            raise AssertionError("Completed SLA outcome count mismatch")
        if r["test_tasks_finished"]+r["test_unfinished"]!=r["test_tasks_admitted"]:
            raise AssertionError("Censored tasks must be conserved")
    records=[]
    for method in METHODS:
        row=by[method]
        same=row["test_finished_work_signature"]==base["test_finished_work_signature"]
        carbon_pct=(
            100*(row["test_total_carbon_kg"]/base["test_total_carbon_kg"]-1)
            if same else None
        )
        reviewed=row["test_guard_reviewed_batches"]
        accepted=row["test_guard_accepted_batches"]
        rejected=sum(row[f] for f in (
            "test_guard_rejected_risk","test_guard_rejected_no_gain",
            "test_guard_rejected_forced"
        ))
        if reviewed!=accepted+rejected:
            raise AssertionError("Guard accept/reject accounting mismatch")
        if method in ("guard0","guard15") and reviewed<=0:
            raise AssertionError("Guard did not evaluate heldout admissions")
        if method not in ("guard0","guard15") and reviewed!=0:
            raise AssertionError("Non-guard policy performed guard reviews")
        if method in ("guard0","guard15") and accepted!=row["test_joint_batch_plans"]:
            raise AssertionError("Accepted batch must run exactly one joint plan")
        records.append({
            "month":row["calendar_month"],"day":row["calendar_day"],
            "seed":row["seed"],"capacity_scale":row["capacity_scale"],
            "window_index":row["window_index"],
            "method":method,
            "admitted":row["test_tasks_admitted"],
            "finished":row["test_tasks_finished"],
            "on_time":row["test_sla_met"],
            "actual_sla_misses_including_overdue":
                row["test_deadline_failures_including_overdue"],
            "sla_delta_vs_greedy":(
                row["test_deadline_failures_including_overdue"]
                -base["test_deadline_failures_including_overdue"]
            ),
            "unfinished_overdue":row["test_unfinished_overdue"],
            "same_completed_work":same,
            "actual_total_carbon_kg_raw":row["test_total_carbon_kg"],
            "carbon_delta_pct_if_identical_work":carbon_pct,
            "routing_changed":row["test_routing_signature"]!=base["test_routing_signature"],
            "guard_reviewed_batches":reviewed,
            "guard_accepted_batches":accepted,
            "guard_rejected_risk":row["test_guard_rejected_risk"],
            "guard_rejected_no_gain":row["test_guard_rejected_no_gain"],
            "guard_rejected_forced":row["test_guard_rejected_forced"],
            "projected_carbon_proxy_delta_accepted":
                row["test_guard_projected_carbon_delta_accepted"],
        })
    return records


def transfer(month,day,seeds,scales,starts,output):
    if (month,day) not in ((11,1),(12,1)):
        raise ValueError("Only predeclared new November/December periods allowed")
    if not seeds or len(set(seeds))!=len(seeds):
        raise ValueError("Distinct nonempty paired seeds required")
    scales=verify_scales(scales)
    plan=planned_folds(test_starts=starts)
    records=[]
    for scale in scales:
        for window in plan["test_windows"]:
            for seed in seeds:
                arms=[]
                for method in METHODS:
                    r,_=run_one(
                        seed,"fixed_30",
                        calibration_steps=16,
                        gap_steps=window["test_gap_steps"],
                        test_steps=16,drain_steps=96,
                        capacity_scale=scale,sim_duration_days=7,
                        fixed_policy_without_calibration=True,
                        calendar_month=month,calendar_day=day,
                        heldout_batch_planner=method
                    )
                    if (r["calendar_month"],r["calendar_day"])!=(month,day):
                        raise AssertionError("Mismatched calendar workload slice")
                    r["window_index"]=window["index"]
                    arms.append(r)
                paired=evaluate_group(arms)
                records.extend(paired)
                for row in paired:
                    print(json.dumps({"phase":"PROJECTED_GUARD_TRANSFER",**row},
                                     allow_nan=False),flush=True)
    target=Path(output)
    target.parent.mkdir(exist_ok=True,parents=True)
    evidence={
        "protocol":"fixed_guard0_guard15_november_december_transfer",
        "period":f"2023-{month:02d}-{day:02d}",
        "workload_year":2020,
        "source_dataset":"Alibaba-2020 workload (same dataset as earlier months)",
        "methods":list(METHODS),"capacity_scales":list(scales),
        "seeds":list(seeds),"windows":plan,
        "predeclared":{
            "queue":"FIFO","fixed_margin_minutes":30,
            "beam_width":4,"beam_chunk_size":8,
            "guard0_max_projected_delay_minutes":0,
            "guard15_max_projected_delay_minutes":15,
            "guard15_maintain_full_30minute_buffer":True,
            "no_training_arrivals":True
        },
        "records":records,
        "limitations":(
            "Predecision queue predictions omit future arrivals and are "
            "not calibrated probability bounds. A guarantee that projected "
            "completion times do not worsen is NOT a guarantee of actual "
            "SLA nonworsening. Two seeds and one workload source are not "
            "independent dataset replication or formal confidence coverage. "
            "Unknown completion predictions cannot certify feasibility. "
            "Emissions comparisons require identical completed job sets."
        ),
    }
    target.write_text(json.dumps(evidence,indent=2,allow_nan=False),
                      encoding="utf-8")
    with target.with_suffix(".csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    return evidence


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--month",type=int,required=True)
    p.add_argument("--day",type=int,default=1)
    p.add_argument("--seeds",nargs="+",type=int,default=[1,42])
    p.add_argument("--capacity-scales",nargs="+",type=float,default=[.02,.1])
    p.add_argument("--test-start-ticks",nargs="+",type=int,default=[288,448])
    p.add_argument("--output",type=Path,default=ROOT/"research_sci/results/projected_guard.json")
    args=p.parse_args()
    transfer(args.month,args.day,args.seeds,args.capacity_scales,
             tuple(args.test_start_ticks),args.output)


if __name__=="__main__":
    main()
