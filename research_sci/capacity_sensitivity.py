"""Exploratory resource-pressure generalization of ONE validation-locked margin.

Selection is based ONLY on an earlier validation cohort at capacity=0.02,
then frozen across the other capacity settings and two later windows.
Each scenario is a separate replay, not a continuing production trace.
Same-seed paired comparisons check admitted jobs, training history,
and IDENTICAL COMPLETED TASK SET before comparing carbon efficiency.
"""
import argparse
import csv
import json
from pathlib import Path

from research_sci.chronological_eval import ROOT, TREATMENTS, run_one
from research_sci.nested_validation import select_validation, audit_pair
from research_sci.temporal_robustness import planned_folds, window_summary


def verify_scales(scales):
    items=tuple(float(v) for v in scales)
    if len(items)<2 or len(set(items))!=len(items):
        raise ValueError("At least two distinct predeclared capacity settings required")
    if any(not 0<v<=1 for v in items) or tuple(sorted(items))!=items:
        raise ValueError("Capacity scales must be increasing and within (0,1]")
    return items


def summarize_sensitivity(rows, selection):
    keyed={}
    for r in rows:
        key=(r["capacity_scale"],r["window_index"])
        keyed.setdefault(key,[]).append(r)
    return [
        dict(capacity_scale=scale,**window_summary(group,selection,window))
        for (scale,window),group in sorted(keyed.items())
    ]


def run_capacity_sweep(seeds, output, scales=(.02,.05,.1),
                       test_starts=(288,448), validation_scale=.02):
    if not seeds or len(seeds)!=len(set(seeds)):
        raise ValueError("Require unique seeds")
    scales=verify_scales(scales)
    if validation_scale not in scales:
        raise ValueError("Validation capacity must be among predeclared scales")
    plan=planned_folds(test_starts=test_starts)
    validation=[]
    for seed in seeds:
        for treatment in TREATMENTS:
            row,_=run_one(seed,treatment,calibration_steps=16,gap_steps=128,
                          test_steps=16,drain_steps=96,
                          capacity_scale=validation_scale,sim_duration_days=7)
            validation.append(row)
    selection,validation_diagnostics=select_validation(validation)
    print(json.dumps({"phase":"CAPACITY_SELECTION_LOCKED",
          "validation_capacity":validation_scale,"selection":selection,
          "diagnostics":validation_diagnostics}),flush=True)
    heldout=[]
    for scale in scales:
        for window in plan["test_windows"]:
            for seed in seeds:
                comparisons={}
                for treatment in dict.fromkeys(("fixed_30",selection)):
                    row,_=run_one(seed,treatment,calibration_steps=16,
                          gap_steps=window["test_gap_steps"],
                          test_steps=16,drain_steps=96,capacity_scale=scale,
                          sim_duration_days=7)
                    row["window_index"]=window["index"]
                    row["absolute_window_start_tick"]=window["test_start_tick"]
                    heldout.append(row)
                    comparisons[treatment]=row
                    print(json.dumps({"phase":"CAPACITY_TEST","capacity":scale,
                         "window":window["index"],"seed":seed,
                         "treatment":treatment,
                         "carbon_kg":row["test_total_carbon_kg"],
                         "admitted":row["test_tasks_admitted"],
                         "completed":row["test_tasks_finished"],
                         "deadline_failures":row["test_deadline_failures_including_overdue"],
                         "completed_work_digest":row["test_finished_work_signature"][:12]}),
                         flush=True)
                audit_pair(comparisons["fixed_30"],comparisons[selection],
                           selection,window["test_gap_steps"])
    summaries=summarize_sensitivity(heldout,selection)
    for entry in summaries:
        print(json.dumps({"phase":"CAPACITY_WINDOW_SUMMARY",**entry},
                         allow_nan=False),flush=True)
    output=Path(output)
    result={
        "protocol":"single_validation_lock_then_2x3_heldout_capacity_window_grid",
        "seeds":list(seeds),"validation_scale":validation_scale,
        "scales":list(scales),"plan":plan,
        "selected_on_validation_only":selection,
        "validation_diagnostics":validation_diagnostics,
        "heldout_rows":heldout,"sensitivity_summaries":summaries,
        "warning":(
            "Synthetic capacity, independent no-arrivals-between-windows replays. "
            "Zero causal evidence for a new algorithm; no capacity-specific "
            "test-time retuning. Carbon deltas null unless completed task SETS match."
        ),
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    with output.with_suffix(".csv").open("w",newline="",encoding="utf-8") as handle:
        keys=list(dict.fromkeys(k for row in heldout for k in row))
        writer=csv.DictWriter(handle,fieldnames=keys)
        writer.writeheader()
        writer.writerows(heldout)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seeds",type=int,nargs="+",default=[1,42])
    p.add_argument("--capacity-scales",type=float,nargs="+",default=[.02,.05,.1])
    p.add_argument("--test-start-ticks",type=int,nargs="+",default=[288,448])
    p.add_argument("--output",type=Path,
                   default=ROOT/"research_sci/results/capacity_sensitivity.json")
    args=p.parse_args()
    run_capacity_sweep(args.seeds,args.output,scales=args.capacity_scales,
                       test_starts=tuple(args.test_start_ticks))


if __name__=="__main__":
    main()
