"""Counterbalanced indexed-vs-legacy queue predictor validation.

Requires identical task-level scheduling across BOTH algorithm orders and
all paired policies. Timing direction is always preserved, never filtered.
This is descriptive host timing, not statistical speedup evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from research.planner_overhead_audit import audit_planner_rows
from research.paired_task_analysis import compare_task_rows

LEGACY = "queue_nsga2_with_transit"
INDEXED = "queue_nsga2_indexed_transit"
ORDERS = ("forward", "reverse")


def audit_counterbalanced(results, completed_tasks):
    """Compare two orderings, return paired per-seed timing and exact task audit."""
    if set(results) != set(ORDERS) or set(completed_tasks) != set(ORDERS):
        raise AssertionError("both forward and reverse runs required")
    seed_groups = {}
    for order in ORDERS:
        groups = {}
        for row in results[order]:
            groups.setdefault(int(row["seed"]), []).append(row)
        if not groups:
            raise AssertionError("empty scenario")
        for seed, rows in groups.items():
            if len(rows) != 2 or {r["policy"] for r in rows} != {LEGACY, INDEXED}:
                raise AssertionError("missing or duplicate policy in seed group")
            audit_planner_rows(rows)
        seed_groups[order] = groups
    if set(seed_groups["forward"]) != set(seed_groups["reverse"]):
        raise AssertionError("different seeds across orders")

    report = []
    for seed in sorted(seed_groups["forward"]):
        # Compare across both execution orders and both algorithm variants.
        task_rows = []
        for order in ORDERS:
            for task in completed_tasks[order]:
                if int(task["seed"]) == seed:
                    tagged = dict(task)
                    tagged["policy"] = f'{task["policy"]}@{order}'
                    task_rows.append(tagged)
        comparisons = compare_task_rows(task_rows, reference=f"{LEGACY}@forward")
        if len(comparisons) != 3:
            raise AssertionError("missing one or more task-level policy comparisons")
        if any(x[key] != 0 for x in comparisons for key in (
                "sla_harmed", "sla_rescued", "destination_changes",
                "start_time_changes", "finish_time_changes")):
            raise AssertionError("indexed and counterbalanced routes differ")

        timing_by_order = {}
        for order in ORDERS:
            rows = {r["policy"]: r for r in seed_groups[order][seed]}
            old, new = rows[LEGACY], rows[INDEXED]
            if old["tasks_dispatched"] != new["tasks_dispatched"]:
                raise AssertionError("unmatched job count")
            for key in ("tasks_dispatched", "sla_violated",
                        "reported_total_carbon_kg", "reported_total_cost_usd",
                        "forecast_mae_minutes", "nsga2_evaluation_requests"):
                if old[key] != new[key]:
                    raise AssertionError(f"within-order mismatch in {key}")
            for key in ("reported_total_carbon_kg", "reported_total_cost_usd",
                        "sla_violated"):
                if old[key] != seed_groups["forward"][seed][0][key]:
                    # No cross-order effects may be attributed to the queue index.
                    raise AssertionError(f"cross-order simulation outcome mismatch {key}")
            p95_old = float(old["planner_dispatch_p95_ms"])
            p95_new = float(new["planner_dispatch_p95_ms"])
            ms_old = float(old["planner_dispatch_ms_per_task"])
            ms_new = float(new["planner_dispatch_ms_per_task"])
            proj_old = float(old["planner_projection_seconds"])
            proj_new = float(new["planner_projection_seconds"])
            if any(not math.isfinite(x) or x < 0 for x in
                   (p95_old, p95_new, ms_old, ms_new, proj_old, proj_new)):
                raise AssertionError("nonfinite or negative timing")
            timing_by_order[order] = {
                "legacy_p95_ms": p95_old,
                "indexed_p95_ms": p95_new,
                "p95_delta_ms": p95_new - p95_old,
                "per_task_delta_ms": ms_new - ms_old,
                "projection_delta_seconds": proj_new - proj_old,
            }
        # Verify all policies, both orders use the same admitted cohort.
        admitted = {int(r["tasks_dispatched"]) for order in ORDERS
                    for r in seed_groups[order][seed]}
        if len(admitted) != 1 or len(task_rows) != 4 * next(iter(admitted)):
            raise AssertionError("cross-order completed task cohort mismatch")
        report.append({
            "seed": seed, "tasks_per_policy": next(iter(admitted)),
            "exact_task_level_equality": True, "orders": timing_by_order,
        })
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prefix", required=True, type=Path,
                   help="Common stem for _forward and _reverse run outputs")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    results, tasks = {}, {}
    for order in ORDERS:
        stem = str(args.prefix) + "_" + order
        results[order] = json.loads(Path(stem + ".json").read_text(encoding="utf8"))
        with Path(stem + "_completed_tasks.csv").open(
                newline="", encoding="utf8") as f:
            tasks[order] = list(csv.DictReader(f))
    report = audit_counterbalanced(results, tasks)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                           encoding="utf8")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
