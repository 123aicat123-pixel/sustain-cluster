"""Validate nonempty dispatch latency and comparable optimizer requests.

A timing smoke cannot establish hardware-independent relative efficiency.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def audit_planner_rows(rows):
    if not rows:
        raise AssertionError("no planner results")
    names = [row["policy"] for row in rows]
    if len(names) != len(set(names)):
        raise AssertionError("duplicate policies in one smoke audit")
    # A fast planner that leaves jobs unresolved is not a fair speed win.
    # All policies in one smoke must share the scenario, seed and admitted
    # cohort size. Exact task identity belongs to paired-task audits.
    cohort_fields = (
        "seed", "scenario_start_month", "scenario_start_day",
        "cpu_capacity_scale", "tasks_dispatched"
    )
    for field in cohort_fields:
        if len({str(row[field]) for row in rows}) != 1:
            raise AssertionError(f"unmatched planner cohorts: {field}")
    report = []
    for row in rows:
        dispatched = int(row["tasks_dispatched"])
        finished = int(row["tasks_finished"])
        if dispatched <= 0 or finished != dispatched:
            raise AssertionError("planner comparison has unfinished task cohort")
        if int(row["unfinished_dispatched"]) != 0:
            raise AssertionError("planner comparison has unresolved tasks")
        if int(row["fallback_assignments"]) != 0:
            raise AssertionError("planner comparison has fallback actions")
        if not bool(row["fully_drained"]) or not bool(row["lifecycle_conserved"]):
            raise AssertionError("planner comparison failed lifecycle completion")
        calls = int(row["planner_dispatch_calls"])
        tasks = int(row["planner_dispatched_tasks"])
        duration = float(row["planner_dispatch_seconds"])
        if calls <= 0 or tasks <= 0 or tasks < calls or tasks != dispatched:
            raise AssertionError("missing planner dispatch coverage")
        if not math.isfinite(duration) or duration < 0:
            raise AssertionError("invalid planner wall time")
        for key in ("planner_dispatch_mean_ms", "planner_dispatch_p50_ms",
                    "planner_dispatch_p95_ms", "planner_dispatch_max_ms",
                    "planner_dispatch_ms_per_task"):
            v = float(row[key])
            if not math.isfinite(v) or v < 0:
                raise AssertionError(f"invalid timing metric {key}")
        p50 = float(row["planner_dispatch_p50_ms"])
        p95 = float(row["planner_dispatch_p95_ms"])
        maximum = float(row["planner_dispatch_max_ms"])
        if not 0 <= p50 <= p95 <= maximum + 1e-9:
            raise AssertionError("planner percentile order failed")
        if not math.isclose(
            float(row["planner_dispatch_ms_per_task"]),
            1000 * duration / tasks, rel_tol=1e-8, abs_tol=1e-8
        ):
            raise AssertionError("task normalized timing inconsistent")
        requests = int(row["nsga2_evaluation_requests"])
        if "nsga2" in row["policy"] and requests <= 0:
            raise AssertionError("NSGA-II without evaluation requests")
        if "nsga2" not in row["policy"] and requests != 0:
            raise AssertionError("non-NSGA-II reported search requests")
        report.append({
            "policy": row["policy"],
            "planner_calls": calls, "tasks": tasks,
            "p50_ms": p50, "p95_ms": p95,
            "ms_per_task": float(row["planner_dispatch_ms_per_task"]),
            "nsga2_evaluation_requests": requests,
        })
    optimizers = [
        r["nsga2_evaluation_requests"] for r in report if "nsga2" in r["policy"]
    ]
    if len(optimizers) > 1 and len(set(optimizers)) != 1:
        raise AssertionError("unmatched optimizer evaluation request budget")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.input.read_text(encoding="utf8"))
    report = audit_planner_rows(rows)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf8"
    )
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
