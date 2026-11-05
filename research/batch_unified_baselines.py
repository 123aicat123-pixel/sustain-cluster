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
from research.csv_export_schema import union_csv_fieldnames
from research.batch_metrics import METRICS, summarize

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
    parser.add_argument("--record-facility-telemetry", action="store_true",
                        help="Write post-step DC+time energy/carbon telemetry (audit only)")
    args = parser.parse_args()
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("--seeds must be nonempty and unique")
    if not args.policies or len(set(args.policies)) != len(args.policies):
        parser.error("--policies must be nonempty and unique")
    results = []
    completed_rows = []
    prediction_rows = []
    facility_rows = []
    # Run every policy with each identical seed, avoiding random generator
    # coupling between consecutive policies.
    for seed in args.seeds:
        for policy in args.policies:
            row = run(policy, seed, args.steps, drain_steps=args.drain_steps, completed_records=completed_rows, cpu_capacity_scale=args.cpu_capacity_scale, start_month=args.start_month, start_day=args.start_day, prediction_records=prediction_rows,
                      facility_records=facility_rows if args.record_facility_telemetry else None)
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
    forecastpath=Path(str(prefix)+"_queue_predictions.csv")
    jsonpath.write_text(json.dumps(results,indent=2,allow_nan=False),encoding="utf8")
    with csvpath.open("w",newline="",encoding="utf8") as f:
        writer=csv.DictWriter(f,fieldnames=union_csv_fieldnames(results))
        writer.writeheader()
        writer.writerows(results)
    if completed_rows:
        with taskspath.open("w", newline="", encoding="utf8") as f:
            detail=csv.DictWriter(f,fieldnames=list(completed_rows[0]))
            detail.writeheader()
            detail.writerows(completed_rows)
    if prediction_rows:
        with forecastpath.open("w", newline="", encoding="utf8") as f:
            detail=csv.DictWriter(f,fieldnames=list(prediction_rows[0]))
            detail.writeheader()
            detail.writerows(prediction_rows)
    if args.record_facility_telemetry:
        from research.facility_telemetry import verify_facility_telemetry
        audit=verify_facility_telemetry(facility_rows,results)
        facility_path=Path(str(prefix)+"_facility_cells.csv")
        if not facility_rows:
            raise AssertionError("facility telemetry enabled without any cells")
        with facility_path.open("w", newline="", encoding="utf8") as f:
            writer=csv.DictWriter(f,fieldnames=union_csv_fieldnames(facility_rows))
            writer.writeheader()
            writer.writerows(facility_rows)
        audit_path=Path(str(prefix)+"_facility_audit.json")
        audit_path.write_text(json.dumps(audit,indent=2,allow_nan=False)+"\\n",
                              encoding="utf8")
        print("Wrote facility telemetry",facility_path,audit_path)
    summary=summarize(results)
    summarypath.write_text(json.dumps(summary,indent=2,allow_nan=False),encoding="utf8")
    print("Wrote",str(jsonpath),str(csvpath),str(summarypath),str(taskspath))
    print("CAUTION: any unfinished tasks, including overdue ones, are separately counted; observational cost/emissions continue during drain. Exploration only.")


if __name__=="__main__":
    main()
