"""Audit a frozen transit-aware prospective experiment without censoring bias.

This is only a task-cohort / simulator-outcome consistency test.
No emissions calibration, cross-date significance or future-input access.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from research.paired_task_analysis import compare_task_rows


POLICIES = ("queue_nsga2_no_queue", "queue_nsga2", "queue_nsga2_with_transit")
SEEDS = (901, 1701)


def audit_scenario(rows, task_rows, *, month, day, cpu_scale,
                   seeds=SEEDS, policies=POLICIES):
    """Full-cohort rankings only for fully completed, fallback-free seed pairs."""
    records = {}
    for r in rows:
        key = (int(r["seed"]), str(r["policy"]))
        if key in records:
            raise AssertionError(f"duplicate run {key}")
        records[key] = r
    expected = {(s, p) for s in seeds for p in policies}
    if set(records) != expected:
        raise AssertionError(f"missing/unexpected runs {expected ^ set(records)}")
    results = []
    for seed in seeds:
        group = [records[seed, policy] for policy in policies]
        for r in group:
            if int(r["scenario_start_month"]) != month or int(r["scenario_start_day"]) != day:
                raise AssertionError("calendar mismatch")
            if not math.isclose(float(r["cpu_capacity_scale"]), cpu_scale, abs_tol=1e-12):
                raise AssertionError("capacity mismatch")
            if not bool(r["lifecycle_conserved"]):
                raise AssertionError("lifecycle invariant failed")
            if int(r["task_audit_completed"]) != int(r["tasks_finished"]):
                raise AssertionError("task-level SLA audit mismatch")
            if int(r["sla_met"]) + int(r["sla_violated"]) != int(r["tasks_finished"]):
                raise AssertionError("SLA counts do not reconcile")
            if r["policy"] in ("queue_nsga2", "queue_nsga2_with_transit"):
                if int(r["forecast_count"]) != int(r["tasks_finished"]):
                    raise AssertionError("missing forecast rows")
                if int(r["forecast_actual_sla_misses"]) != int(r["sla_violated"]):
                    raise AssertionError("forecast vs independently observed SLA mismatch")
        admitted = {int(r["tasks_dispatched"]) for r in group}
        if len(admitted) != 1:
            raise AssertionError(f"unmatched admission counts seed={seed}")
        completed = all(
            int(r["unfinished_dispatched"]) == 0
            and int(r["fallback_assignments"]) == 0
            and int(r["tasks_finished"]) == int(r["tasks_dispatched"])
            and bool(r["fully_drained"])
            for r in group
        )
        eligible = completed and next(iter(admitted)) > 0
        out = {"seed": seed, "eligible": eligible,
               "admitted_count": next(iter(admitted)),
               "reason": None if eligible else "unfinished/fallback/empty cohort",
               "raw_policies": [
                   {"name": r["policy"],
                    "tasks_finished": int(r["tasks_finished"]),
                    "unfinished": int(r["unfinished_dispatched"]),
                    "fallback": int(r["fallback_assignments"]),
                    "sla_misses": int(r["sla_violated"]),
                    "cost_usd": float(r["reported_total_cost_usd"]),
                    "carbon_kg": float(r["reported_total_carbon_kg"]),
                    "start_mae_min": r.get("forecast_mae_minutes"),
                    "false_safe_count": r.get("forecast_false_safe_count")}
                   for r in group]}
        if eligible:
            completed_rows = [r for r in task_rows if int(r["seed"]) == seed]
            if len(completed_rows) != next(iter(admitted)) * len(policies):
                raise AssertionError("missing completed-task records")
            pairs = compare_task_rows(completed_rows, reference="queue_nsga2")
            if len(pairs) != len(policies)-1:
                raise AssertionError("missing paired comparisons")
            reference_misses = int(records[seed, "queue_nsga2"]["sla_violated"])
            changes = []
            for p in pairs:
                candidate = records[seed, p["policy"]]
                difference = int(candidate["sla_violated"]) - reference_misses
                if difference != p["sla_harmed"] - p["sla_rescued"]:
                    raise AssertionError("paired SLA arithmetic mismatch")
                changes.append({
                    "policy": p["policy"], "against": "queue_nsga2",
                    "rescued": p["sla_rescued"], "harmed": p["sla_harmed"],
                    "sla_misses_delta": difference,
                    "carbon_kg_delta": float(candidate["reported_total_carbon_kg"])
                        -float(records[seed,"queue_nsga2"]["reported_total_carbon_kg"]),
                    "cost_usd_delta": float(candidate["reported_total_cost_usd"])
                        -float(records[seed,"queue_nsga2"]["reported_total_cost_usd"]),
                })
            out["paired_outcomes"] = changes
        results.append(out)
    return results


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prefix",required=True,type=Path)
    p.add_argument("--month",required=True,type=int)
    p.add_argument("--day",required=True,type=int)
    p.add_argument("--cpu-scale",required=True,type=float)
    args=p.parse_args()
    stem=str(args.prefix)
    rows=json.loads(Path(stem+".json").read_text(encoding="utf8"))
    with Path(stem+"_completed_tasks.csv").open(newline="",encoding="utf8") as f:
        tasks=list(csv.DictReader(f))
    report=audit_scenario(rows,tasks,month=args.month,day=args.day,cpu_scale=args.cpu_scale)
    Path(stem+"_prospective_audit.json").write_text(
        json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf8")
    print(json.dumps(report,indent=2,allow_nan=False))
    print("Every noneligible condition is CENSORED: no full-cohort ranking.")


if __name__=="__main__":
    main()
