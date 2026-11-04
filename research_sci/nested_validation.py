"""Validation-only selection, then locked later chronological test replay.

Test replay omits validation admissions during the gap, so this is a
controlled counterfactual at later clock time, NOT continuous production.
"""
import argparse
import csv
import json
from pathlib import Path
from research_sci.chronological_eval import ROOT, TREATMENTS, run_one
from research_sci.risk_frontier import validate_paired


def plan_windows(cal_steps, gap_val, val_steps, gap_test, test_steps, drain_steps):
    vals = (cal_steps, gap_val, val_steps, gap_test, test_steps, drain_steps)
    if any(not isinstance(x, int) or x < 1 for x in vals):
        raise ValueError("All windows must use positive integer ticks")
    val_begin = cal_steps + gap_val
    val_end = val_begin + val_steps
    test_begin = val_end + gap_test
    if test_begin + test_steps + drain_steps > 672:
        raise ValueError("Outside seven-day simulator horizon")
    return {"cal_steps": cal_steps, "val_begin": val_begin,
            "val_end": val_end, "test_begin": test_begin,
            "test_gap": gap_val + val_steps + gap_test}


def select_validation(rows):
    """Non-inferior deadline misses for EVERY seed, then least mean carbon."""
    grouped = validate_paired(rows)
    seeds = sorted({r["seed"] for r in rows})
    eligible = []
    diagnostics = []
    for i, treatment in enumerate(TREATMENTS):
        candidate = [grouped[(seed, treatment)] for seed in seeds]
        baseline = [grouped[(seed, "fixed_30")] for seed in seeds]
        equal_work = all(
            x["test_tasks_finished"] == b["test_tasks_finished"]
            and x.get("test_finished_work_signature") is not None
            and x["test_finished_work_signature"] == b.get("test_finished_work_signature")
            for x,b in zip(candidate, baseline))
        sla_ok = all(
            x["test_deadline_failures_including_overdue"]
            <= b["test_deadline_failures_including_overdue"]
            for x,b in zip(candidate, baseline))
        carbon = sum(x["test_total_carbon_kg"] for x in candidate) / len(candidate)
        diagnostics.append({"treatment": treatment, "equal_work": equal_work,
                            "sla_nonworse_each_seed": sla_ok,
                            "mean_carbon_kg": carbon})
        if equal_work and sla_ok:
            eligible.append((carbon, i, treatment))
    if not eligible:
        raise AssertionError("Baseline must qualify")
    return min(eligible)[2], diagnostics


def audit_pair(base, chosen, selected, expected_gap):
    for field in ("seed", "train_window_start", "train_admissions_end",
                  "test_window_start", "test_admissions_end",
                  "train_routing_signature", "train_admission_signature",
                  "test_admission_signature", "test_tasks_admitted",
                  "pretest_train_completed", "pretest_learned_buffer_minutes",
                  "calibration_steps", "test_steps", "drain_steps", "gap_steps"):
        if base[field] != chosen[field]:
            raise AssertionError("Unmatched holdout: " + field)
    if base["gap_steps"] != expected_gap:
        raise AssertionError("Wrong later test time")
    if base["applied_frozen_buffer_minutes"] != 30:
        raise AssertionError("Baseline buffer changed")
    if chosen["treatment"] != selected:
        raise AssertionError("Validation choice not locked")
    if not base["pretest_training_sample_is_disjoint"]:
        raise AssertionError("Leaked calibration tasks")


def run_experiment(seeds, output, cal_steps=16, gap_val=128,
                   val_steps=16, gap_test=128, test_steps=16,
                   drain_steps=96, capacity=.02):
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("Require unique seeds")
    plan = plan_windows(cal_steps,gap_val,val_steps,gap_test,test_steps,drain_steps)
    validation = []
    for seed in seeds:
        for treatment in TREATMENTS:
            row,_ = run_one(seed,treatment,calibration_steps=cal_steps,
                            gap_steps=gap_val,test_steps=val_steps,
                            drain_steps=drain_steps,capacity_scale=capacity)
            validation.append(row)
            print(json.dumps({"phase":"validation","seed":seed,"policy":treatment,
                "misses":row["test_deadline_failures_including_overdue"],
                "carbon":row["test_total_carbon_kg"]}),flush=True)
    selected, diagnostic = select_validation(validation)
    print(json.dumps({"phase":"LOCKED_PRE_TEST","selected":selected,
                      "validation_diagnostics":diagnostic}),flush=True)
    heldout=[]
    for seed in seeds:
        treatments = list(dict.fromkeys(("fixed_30", selected)))
        for treatment in treatments:
            row,_=run_one(seed,treatment,calibration_steps=cal_steps,
                          gap_steps=plan["test_gap"],test_steps=test_steps,
                          drain_steps=drain_steps,capacity_scale=capacity)
            heldout.append(row)
            print(json.dumps({"phase":"HELDOUT","seed":seed,
                "policy":treatment,"carbon":row["test_total_carbon_kg"],
                "misses":row["test_deadline_failures_including_overdue"],
                "completed":row["test_tasks_finished"],
                "safe_flags":row["test_decision_margin_predicted_safe_completed"]
            }),flush=True)
    paired={(r["seed"],r["treatment"]):r for r in heldout}
    for seed in seeds:
        audit_pair(paired[(seed,"fixed_30")],paired[(seed,selected)],
                   selected,plan["test_gap"])
    baseline_rows=[paired[(seed,"fixed_30")] for seed in seeds]
    selected_rows=[paired[(seed,selected)] for seed in seeds]
    equal_finished=all(
        a["test_tasks_finished"] == b["test_tasks_finished"]
        and a.get("test_finished_work_signature") is not None
        and a["test_finished_work_signature"] == b.get("test_finished_work_signature")
        for a,b in zip(baseline_rows,selected_rows)
    )
    test_diagnostic={
        "equal_completed_work_each_seed":equal_finished,
        "same_completed_job_count_each_seed": all(
            a["test_tasks_finished"] == b["test_tasks_finished"]
            for a,b in zip(baseline_rows, selected_rows)
        ),
        "baseline_mean_carbon_kg":sum(x["test_total_carbon_kg"] for x in baseline_rows)/len(seeds),
        "selected_mean_carbon_kg":sum(x["test_total_carbon_kg"] for x in selected_rows)/len(seeds),
        "baseline_mean_deadline_failures":sum(x["test_deadline_failures_including_overdue"] for x in baseline_rows)/len(seeds),
        "selected_mean_deadline_failures":sum(x["test_deadline_failures_including_overdue"] for x in selected_rows)/len(seeds),
        "comparison_interpretation":(
            "equal completed work" if equal_finished
            else "unequal completed work; carbon efficiency not directly comparable"
        ),
        "selection_not_updated_after_test":True,
    }
    print(json.dumps({"phase":"INDEPENDENT_TEST_SUMMARY",**test_diagnostic},
                     allow_nan=False),flush=True)
    result={"plan":plan,"seeds":list(seeds),"selected_on_validation":selected,
            "test_diagnostic":test_diagnostic,
            "selection_diagnostics":diagnostic,"validation_rows":validation,
            "heldout_rows":heldout,"holdout_used_in_selection":False,
            "validation_admissions_omitted_in_test_replay":True,
            "warning":"Exploratory two-seed synthetic stress; no formal risk guarantee."}
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    for label,rows in (("validation",validation),("heldout",heldout)):
        dest=output.with_name(output.stem+"_"+label+".csv")
        with dest.open("w",newline="",encoding="utf-8") as f:
            cols=list(dict.fromkeys(k for r in rows for k in r))
            writer=csv.DictWriter(f,fieldnames=cols)
            writer.writeheader()
            writer.writerows(rows)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seeds",nargs="+",type=int,default=[1,42])
    p.add_argument("--output",type=Path,default=ROOT/"research_sci/results/nested_validation.json")
    p.add_argument("--capacity-scale",type=float,default=.02)
    args=p.parse_args()
    run_experiment(args.seeds,args.output,capacity=args.capacity_scale)


if __name__=="__main__":
    main()
