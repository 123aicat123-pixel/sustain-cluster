"""Pre-registered multi-window chronological robustness of a locked margin.

Select buffer ONCE using historical calibration and one validation cohort,
then evaluate that exact locked choice on multiple later non-overlapping
time windows. ALL replays use a constant seven-day simulator horizon to
prevent simulation-duration changes from altering their shared training
prefix. Each test replay omits all prior evaluation arrivals: this is
not continuous production, and windows share workload source and seeds.

No heldout result ever participates in the margin-selection procedure.
"""
import argparse
import csv
import json
from pathlib import Path

from research_sci.chronological_eval import ROOT, TREATMENTS, run_one
from research_sci.nested_validation import select_validation, audit_pair


def planned_folds(cal_steps=16, val_gap=128, val_steps=16,
                  test_starts=(288, 448), test_steps=16, drain_steps=96):
    sizes = (cal_steps, val_gap, val_steps, test_steps, drain_steps)
    if any(not isinstance(x, int) or x < 1 for x in sizes):
        raise ValueError("Time segment lengths must be positive integers")
    val_start = cal_steps + val_gap
    val_end = val_start + val_steps
    starts = tuple(test_starts)
    if len(starts) < 2 or tuple(sorted(set(starts))) != starts:
        raise ValueError("Require two or more distinct ordered test starts")
    prev_end = val_end
    windows = []
    for i, start in enumerate(starts):
        if not isinstance(start, int) or start <= prev_end:
            raise ValueError("Test overlaps validation or earlier test-drain window")
        end = start + test_steps + drain_steps
        if end > 672:
            raise ValueError("Test exceeds seven-day horizon")
        windows.append({"index": i, "test_start_tick": start,
                        "admission_end_tick": start + test_steps,
                        "drain_end_tick": end, "test_gap_steps": start - cal_steps})
        prev_end = end
    return {"calibration_steps": cal_steps,
            "validation_start_tick": val_start,
            "validation_end_tick": val_end,
            "fixed_sim_duration_days": 7,
            "test_windows": windows,
            "replays_are_independent_not_continuous": True}


def window_summary(rows, selected, index):
    group = {(r["seed"],r["treatment"]):r for r in rows}
    seeds = sorted({r["seed"] for r in rows})
    expected = {(seed,treatment) for seed in seeds
                for treatment in dict.fromkeys(("fixed_30",selected))}
    if set(group) != expected:
        raise AssertionError("Missing paired test result")
    comparisons=[]
    for seed in seeds:
        base=group[(seed,"fixed_30")]
        chosen=group[(seed,selected)]
        equal=(base["test_tasks_finished"]==chosen["test_tasks_finished"]
               and base["test_tasks_admitted"]==chosen["test_tasks_admitted"])
        comparisons.append({
            "seed":seed,
            "equal_completed_work":equal,
            "reference_carbon_kg":base["test_total_carbon_kg"],
            "chosen_carbon_kg":chosen["test_total_carbon_kg"],
            # Absolute totals are recorded for transparency, but a carbon
            # improvement percentage is NOT interpretable if finished
            # workloads differ. No false 'wins' from unfinished work.
            "carbon_change_kg_if_comparable":(
                chosen["test_total_carbon_kg"]-base["test_total_carbon_kg"]
                if equal else None),
            "carbon_change_pct":(
                100*(chosen["test_total_carbon_kg"]
                     /base["test_total_carbon_kg"]-1) if equal else None),
            "reference_completed":base["test_tasks_finished"],
            "chosen_completed":chosen["test_tasks_finished"],
            "reference_unfinished":base["test_unfinished"],
            "chosen_unfinished":chosen["test_unfinished"],
            "reference_overdue_unfinished":base["test_unfinished_overdue"],
            "chosen_overdue_unfinished":chosen["test_unfinished_overdue"],
            "reference_deadline_failures":base["test_deadline_failures_including_overdue"],
            "chosen_deadline_failures":chosen["test_deadline_failures_including_overdue"],
            "change_in_deadline_failures":(
                chosen["test_deadline_failures_including_overdue"]
                -base["test_deadline_failures_including_overdue"]
            ),
            "test_tasks_admitted":base["test_tasks_admitted"],
        })
    n=len(comparisons)
    comparable=all(r["equal_completed_work"] for r in comparisons)
    return {
        "window_index":index,
        "paired_results":comparisons,
        "all_seeds_same_completed_work":comparable,
        "mean_carbon_delta_pct": (
            sum(r["carbon_change_pct"] for r in comparisons)/n if comparable else None),
        "mean_deadline_failure_delta":(
            sum(r["change_in_deadline_failures"] for r in comparisons)/n),
        "both_objectives_nonworse_for_every_seed":(
            comparable and all(r["carbon_change_kg_if_comparable"]<=0
                               and r["change_in_deadline_failures"]<=0
                               for r in comparisons)),
        "mean_carbon_lower_and_mean_deadline_failures_nonworse":(
            comparable
            and sum(r["carbon_change_kg_if_comparable"] for r in comparisons)<0
            and sum(r["change_in_deadline_failures"] for r in comparisons)<=0),
    }


def run_robustness(seeds, output, cal_steps=16, val_gap=128, val_steps=16,
                   test_starts=(288,448), test_steps=16, drain_steps=96,
                   capacity_scale=.02):
    if not seeds or len(set(seeds))!=len(seeds):
        raise ValueError("Seeds must be unique")
    plan=planned_folds(cal_steps,val_gap,val_steps,test_starts,
                       test_steps,drain_steps)
    validation=[]
    for seed in seeds:
        for treatment in TREATMENTS:
            row,_=run_one(seed,treatment,calibration_steps=cal_steps,
                          gap_steps=val_gap,test_steps=val_steps,
                          drain_steps=drain_steps,capacity_scale=capacity_scale,
                          sim_duration_days=7)
            validation.append(row)
    selected,diagnostics=select_validation(validation)
    print(json.dumps({"phase":"PRE_TEST_LOCK","selected":selected,
                      "validation_diagnostics":diagnostics}),flush=True)
    rows=[]
    summaries=[]
    for window in plan["test_windows"]:
        index=window["index"]
        group=[]
        for seed in seeds:
            val_base=next(r for r in validation if r["seed"]==seed
                          and r["treatment"]=="fixed_30")
            for treatment in dict.fromkeys(("fixed_30",selected)):
                row,_=run_one(seed,treatment,calibration_steps=cal_steps,
                              gap_steps=window["test_gap_steps"],
                              test_steps=test_steps,drain_steps=drain_steps,
                              capacity_scale=capacity_scale,
                              sim_duration_days=7)
                row["window_index"]=index
                row["absolute_window_start_tick"]=window["test_start_tick"]
                if row["train_routing_signature"]!=val_base["train_routing_signature"]:
                    raise AssertionError("Training policy replay changed across windows")
                if row["train_admission_signature"]!=val_base["train_admission_signature"]:
                    raise AssertionError("Training arrivals changed across windows")
                group.append(row)
                rows.append(row)
                print(json.dumps({
                    "phase":"LOCKED_HELDOUT", "window":index,
                    "seed":seed,"treatment":treatment,
                    "misses":row["test_deadline_failures_including_overdue"],
                    "finished":row["test_tasks_finished"],
                    "admitted":row["test_tasks_admitted"],
                    "unfinished":row["test_unfinished"],
                    "overdue_unfinished":row["test_unfinished_overdue"],
                    "carbon_kg":row["test_total_carbon_kg"],
                    "safe_flags":row["test_decision_margin_predicted_safe_completed"],
                    "test_start":row["test_window_start"],
                }),flush=True)
            pairs={(r["seed"],r["treatment"]):r for r in group}
            audit_pair(pairs[(seed,"fixed_30")],pairs[(seed,selected)],
                       selected,window["test_gap_steps"])
        summary=window_summary(group,selected,index)
        summaries.append(summary)
        print(json.dumps({"phase":"LOCKED_WINDOW_SUMMARY",**summary},
                         allow_nan=False),flush=True)
    evidence={
        "method":"validation_locked_two_nonoverlapping_test_windows",
        "seeds":list(seeds),"window_plan":plan,
        "locked_treatment":selected,
        "validation_diagnostics":diagnostics,
        "validation_rows":validation,
        "heldout_rows":rows,
        "heldout_window_summaries":summaries,
        "both_windows_mean_carbon_and_sla_nonworse":all(
            x["mean_carbon_lower_and_mean_deadline_failures_nonworse"]
            for x in summaries),
        "selection_uses_no_heldout_data":True,
        "warning":(
            "Exploratory synthetic stress: shared seeds and training prefix; "
            "independent replays intentionally omit validation and prior test "
            "arrivals. Results do not establish statistical significance."
        ),
    }
    dest=Path(output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(evidence,indent=2,allow_nan=False),encoding="utf-8")
    for label, group in (("validation",validation),("heldout",rows)):
        path=dest.with_name(dest.stem+"_"+label+".csv")
        with path.open("w",newline="",encoding="utf-8") as handle:
            columns=list(dict.fromkeys(k for r in group for k in r))
            writer=csv.DictWriter(handle,fieldnames=columns)
            writer.writeheader()
            writer.writerows(group)
    return evidence


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seeds",nargs="+",type=int,default=[1,42])
    p.add_argument("--test-start-ticks",nargs="+",type=int,default=[288,448])
    p.add_argument("--capacity-scale",type=float,default=.02)
    p.add_argument("--output",type=Path,
                   default=ROOT/"research_sci/results/temporal_robustness.json")
    args=p.parse_args()
    run_robustness(args.seeds,args.output,
                   test_starts=tuple(args.test_start_ticks),
                   capacity_scale=args.capacity_scale)


if __name__=="__main__":
    main()
