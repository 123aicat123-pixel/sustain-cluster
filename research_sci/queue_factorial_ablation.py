"""Factorial ablation to separate queue execution from routing forecast.

We compare four predeclared variants: (FIFO, FIFO), (EDF, FIFO),
(FIFO, EDF), (EDF, EDF), where the first term is actual datacenter
execution queue order and second is dispatch-time predictor order.
Mismatch cases are deliberately diagnostics, not proposed strategies.

The routing forecast is allowed to become mismatched, but it never
sees future task arrivals. All training traffic remains FIFO and
uses the same seed/clock; interventions begin only at test.
This is a FULL matched re-simulation, not a single-job counterfactual.
"""
import argparse
import csv
import json
from pathlib import Path
from research_sci.chronological_eval import ROOT, run_one
from research_sci.temporal_robustness import planned_folds
from research_sci.capacity_sensitivity import verify_scales

CONFIGS=(("fifo","fifo"),("edf","fifo"),("fifo","edf"),("edf","edf"))


def compare_factorial(rows):
    by_combo={(r["queue_discipline"],r["forecast_queue_discipline"]):r
              for r in rows}
    if set(by_combo)!=set(CONFIGS) or len(rows)!=len(CONFIGS):
        raise AssertionError("Incomplete or duplicate 2x2 ablation")
    baseline=by_combo[("fifo","fifo")]
    for item in rows:
        for field in (
            "seed","capacity_scale","test_window_start","test_admissions_end",
            "train_window_start","train_admissions_end",
            "test_tasks_admitted","test_admission_signature",
            "train_routing_signature","train_admission_signature",
            "pretest_train_completed","pretest_learned_buffer_minutes",
            "applied_frozen_buffer_minutes"
        ):
            if baseline[field]!=item[field]:
                raise AssertionError("Unmatched factorial condition: "+field)
    output=[]
    for executor,predictor in CONFIGS:
        row=by_combo[(executor,predictor)]
        same=(row["test_finished_work_signature"]
              ==baseline["test_finished_work_signature"])
        carbon_diff=(
            row["test_total_carbon_kg"]-baseline["test_total_carbon_kg"]
            if same else None
        )
        output.append({
            "seed":row["seed"],"capacity_scale":row["capacity_scale"],
            "window_index":row["window_index"],
            "execution_queue_order":executor,
            "routing_forecast_order":predictor,
            "admitted":row["test_tasks_admitted"],
            "finished":row["test_tasks_finished"],
            "unfinished":row["test_unfinished"],
            "overdue_unfinished":row["test_unfinished_overdue"],
            "actual_sla_failures":row["test_deadline_failures_including_overdue"],
            "sla_delta_to_fifo_fifo":(
                row["test_deadline_failures_including_overdue"]
                -baseline["test_deadline_failures_including_overdue"]
            ),
            "routing_changed_vs_fifo_fifo":(
                row["test_routing_signature"]!=baseline["test_routing_signature"]
            ),
            "identical_completed_work":same,
            "raw_carbon_kg":row["test_total_carbon_kg"],
            "carbon_delta_kg_if_identical_work":carbon_diff,
            "carbon_delta_pct_if_identical_work":(
                carbon_diff*100/baseline["test_total_carbon_kg"]
                if carbon_diff is not None else None
            ),
        })
    return output


def run_ablation(seeds,scales,starts,output):
    if not seeds or len(seeds)!=len(set(seeds)):
        raise ValueError("Require distinct nonempty seeds")
    scales=verify_scales(scales)
    plan=planned_folds(test_starts=starts)
    records=[]
    for scale in scales:
        for window in plan["test_windows"]:
            for seed in seeds:
                group=[]
                for executor,predictor in CONFIGS:
                    row,_=run_one(
                        seed,"fixed_30",calibration_steps=16,
                        gap_steps=window["test_gap_steps"],
                        test_steps=16,drain_steps=96,
                        capacity_scale=scale,sim_duration_days=7,
                        heldout_queue_order=executor,
                        heldout_forecast_order=predictor
                    )
                    row["window_index"]=window["index"]
                    group.append(row)
                output_rows=compare_factorial(group)
                records.extend(output_rows)
                for record in output_rows:
                    print(json.dumps({"phase":"QUEUE_FACTORIAL_RESULT",**record},
                                     allow_nan=False),flush=True)
    report={
        "protocol":"2x2_execution_queue_x_routing_forecast_order",
        "seeds":list(seeds),"capacity_scales":list(scales),
        "windows":plan,"results":records,
        "limitations":(
            "Mismatched execution/forecast variants are diagnostic only. "
            "EDF is a known standard baseline. Every policy is fully re-simulated; "
            "carbon deltas are undefined if exact completed task sets differ. "
            "Gapped independent chronological replays and shared workload/seed "
            "do not establish generalization or causal effect decomposition "
            "without interaction assumptions."
        ),
    }
    output=Path(output)
    output.parent.mkdir(exist_ok=True,parents=True)
    output.write_text(json.dumps(report,indent=2,allow_nan=False),
                      encoding="utf-8")
    with output.with_suffix(".csv").open("w",newline="",encoding="utf-8") as file:
        writer=csv.DictWriter(file,fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--seeds",nargs="+",type=int,default=[1,42])
    parser.add_argument("--capacity-scales",nargs="+",type=float,default=[.02,.1])
    parser.add_argument("--test-start-ticks",nargs="+",type=int,default=[288,448])
    parser.add_argument("--output",type=Path,
        default=ROOT/"research_sci/results/queue_factorial.json")
    args=parser.parse_args()
    run_ablation(args.seeds,args.capacity_scales,
                 tuple(args.test_start_ticks),args.output)


if __name__=="__main__":
    main()
