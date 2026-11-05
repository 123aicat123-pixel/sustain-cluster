"""Matched adaptive-vs-full transit overhead and outcome comparison.

Descriptive audit only. No assertions that adaptive must win: reductions,
regressions and equal outcomes are all retained for publication reporting.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from research.planner_overhead_audit import audit_planner_rows

BASE = "queue_nsga2_with_transit"
ADAPT = "queue_nsga2_adaptive_transit"


def compare_adaptive_runs(rows):
    grouped = {}
    for row in rows:
        key = (
            int(row["scenario_start_month"]), int(row["scenario_start_day"]),
            float(row["cpu_capacity_scale"]), int(row["seed"])
        )
        grouped.setdefault(key, []).append(row)
    if not grouped:
        raise AssertionError("no simulation runs")
    output = []
    for key, group in sorted(grouped.items()):
        valid = {str(r["policy"]): r for r in group}
        if len(valid) != len(group) or BASE not in valid or ADAPT not in valid:
            raise AssertionError(f"missing or duplicate comparison policies {key}")
        audited = audit_planner_rows(group)
        by_name = {r["policy"]: r for r in audited}
        base, candidate = valid[BASE], valid[ADAPT]
        checks = int(candidate["adaptive_projection_checks"])
        skipped = int(candidate["adaptive_base_projections"])
        computed = int(candidate["adaptive_transit_projections"])
        if checks <= 0 or skipped < 0 or computed < 0 or checks != skipped + computed:
            raise AssertionError("invalid adaptive projection counter conservation")
        base_requests = int(base["nsga2_evaluation_requests"])
        candidate_requests = int(candidate["nsga2_evaluation_requests"])
        if base_requests != candidate_requests:
            raise AssertionError("unmatched fixed GA evaluation requests")
        def difference(field):
            x = float(candidate[field]) - float(base[field])
            if not math.isfinite(x):
                raise AssertionError(f"nonfinite outcome {field}")
            return x
        output.append({
            "month": key[0], "day": key[1], "cpu_scale": key[2], "seed": key[3],
            "tasks": int(candidate["tasks_dispatched"]),
            "adaptive_skip_fraction": skipped / checks,
            "adaptive_projection_checks": checks,
            "adaptive_base_projections": skipped,
            "adaptive_transit_projections": computed,
            "evaluation_requests": candidate_requests,
            "p95_ms_delta": by_name[ADAPT]["p95_ms"] - by_name[BASE]["p95_ms"],
            "ms_per_task_delta": (by_name[ADAPT]["ms_per_task"]
                                  - by_name[BASE]["ms_per_task"]),
            "sla_misses_delta": int(candidate["sla_violated"])
                                - int(base["sla_violated"]),
            "carbon_kg_delta": difference("reported_total_carbon_kg"),
            "cost_usd_delta": difference("reported_total_cost_usd"),
            "forecast_mae_min_delta": difference("forecast_mae_minutes"),
            "same_task_level_outcomes_not_asserted": True,
        })
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = compare_adaptive_runs(json.loads(args.input.read_text(encoding="utf8")))
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                           encoding="utf8")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
