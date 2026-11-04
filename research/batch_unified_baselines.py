"""Small multi-seed exploration of adapted SustainCluster rule-based baselines.

Uses the same per-task action path for each policy and reports raw runs,
mean/std, and horizon leftovers. NOT a paper-ready benchmark: no time split,
no end-of-trace drain, and only a few seeds. Never infer statistical superiority
from this smoke experiment.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path

from research.unified_baseline_smoke import run, POLICIES, ROOT

METRICS = (
    "reported_total_cost_usd", "reported_total_carbon_kg",
    "facility_energy_kwh", "tasks_seen", "tasks_started",
    "tasks_finished", "sla_met", "sla_violated",
    "pending_last", "running_last", "in_transit_last",
    "local_dispatches", "remote_dispatches",
    "cpu_capacity_scale", "completion_fraction", "fallback_fraction",
    "undispatched_at_horizon", "fallback_assignments",
    "unfinished_dispatched", "unfinished_overdue_at_horizon",
    "task_audit_sla_violation_rate", "task_audit_response_mean_minutes",
    "task_audit_response_p95_minutes", "task_audit_wait_p95_minutes",
    "task_audit_total_tardiness_minutes",
)


def summarize(results):
    groups = {}
    for row in results:
        groups.setdefault(row["policy"], []).append(row)
    summary = {}
    for policy, runs in groups.items():
        metrics = {}
        for metric in METRICS:
            values = [float(r[metric]) for r in runs if r[metric] is not None]
            if not values:
                metrics[metric] = {"mean": None, "std": None, "min": None, "max": None}
                continue
            metrics[metric] = {
                "mean": statistics.mean(values),
                "std": statistics.stdev(values) if len(values)>1 else None,
                "min": min(values), "max": max(values),
            }
        summary[policy] = {"number_of_seeds": len(runs), "metrics": metrics}
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--drain-steps", type=int, default=0)
    parser.add_argument("--cpu-capacity-scale", type=float, default=1.0)
    parser.add_argument("--start-month", type=int, default=None)
    parser.add_argument("--start-day", type=int, default=None)
    parser.add_argument("--seeds", nargs="+", type=int, default=[1,42,2026])
    parser.add_argument(
        "--policies", nargs="+", choices=sorted(POLICIES),
        default=["lowest_carbon","lowest_price","round_robin"],
    )
    parser.add_argument(
        "--output-prefix", type=Path,
        default=ROOT / "research/results/unified_batch"
    )
    args = parser.parse_args()
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("--seeds must be nonempty and unique")
    if not args.policies or len(set(args.policies)) != len(args.policies):
        parser.error("--policies must be nonempty and unique")
    results = []
    completed_rows = []
    # Run every policy with each identical seed, avoiding random generator
    # coupling between consecutive policies.
    for seed in args.seeds:
        for policy in args.policies:
            row = run(policy, seed, args.steps, drain_steps=args.drain_steps, completed_records=completed_rows, cpu_capacity_scale=args.cpu_capacity_scale, start_month=args.start_month, start_day=args.start_day)
            results.append(row)
            print(f"completed: seed={seed} policy={policy} "
                  f"cost={row['reported_total_cost_usd']:.3f} "
                  f"carbon={row['reported_total_carbon_kg']:.3f} "
                  f"finished={row['tasks_finished']} "
                  f"still_running={row['running_last']} "
                  f"in_transit={row['in_transit_last']} "
                  f"overdue_unfinished={row['unfinished_overdue_at_horizon']} "
                  f"fallback={row['fallback_fraction']:.1%} "
                  f"completion={row['completion_fraction']:.1%}",flush=True)
    prefix=args.output_prefix
    prefix.parent.mkdir(parents=True,exist_ok=True)
    jsonpath=Path(str(prefix)+".json")
    csvpath=Path(str(prefix)+".csv")
    summarypath=Path(str(prefix)+"_summary.json")
    taskspath=Path(str(prefix)+"_completed_tasks.csv")
    jsonpath.write_text(json.dumps(results,indent=2,allow_nan=False),encoding="utf8")
    with csvpath.open("w",newline="",encoding="utf8") as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    if completed_rows:
        with taskspath.open("w", newline="", encoding="utf8") as f:
            detail=csv.DictWriter(f,fieldnames=list(completed_rows[0]))
            detail.writeheader()
            detail.writerows(completed_rows)
    summary=summarize(results)
    summarypath.write_text(json.dumps(summary,indent=2,allow_nan=False),encoding="utf8")
    print("Wrote",str(jsonpath),str(csvpath),str(summarypath),str(taskspath))
    print("CAUTION: any unfinished tasks, including overdue ones, are separately counted; observational cost/emissions continue during drain. Exploration only.")


if __name__=="__main__":
    main()
