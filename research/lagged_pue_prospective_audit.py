"""Prospective lagged-PUE action-conditional proxy *falsification* audit.

This tool does not fit or tune a model, or remove non-improving cases.
Audits every fixed paired seed with complete task matching and reports
candidate-minus-control realized simulator outcomes.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from research.paired_task_analysis import compare_task_rows
from research.planner_overhead_audit import audit_planner_rows

REFERENCE = "queue_nsga2_indexed_transit"
CANDIDATE = "queue_nsga2_lagged_pue"
HEURISTIC = "sla_feasible_carbon"
POLICIES = {REFERENCE, CANDIDATE, HEURISTIC}
SEEDS = {901, 1701}


def _finite(row, key):
    value = float(row[key])
    if not math.isfinite(value):
        raise AssertionError(f"nonfinite {key}")
    return value


def audit_prospective(rows, completed_rows):
    """Analyze one predeclared date × capacity (exactly three policies/seed)."""
    if not rows or not completed_rows:
        raise AssertionError("missing raw simulation or task records")
    groups = defaultdict(list)
    for row in rows:
        seed = int(row["seed"])
        groups[seed].append(row)
    if set(groups) != SEEDS:
        raise AssertionError("missing or unexpected random seeds")
    dates = {(int(row["scenario_start_month"]), int(row["scenario_start_day"]),
              _finite(row, "cpu_capacity_scale")) for row in rows}
    if len(dates) != 1:
        raise AssertionError("mixed workload dates or CPU scales in one audit")
    month, day, scale = next(iter(dates))
    out = []
    for seed in sorted(SEEDS):
        group = groups[seed]
        if len(group) != 3 or {r["policy"] for r in group} != POLICIES:
            raise AssertionError(f"missing or duplicate policy for seed {seed}")
        audit_planner_rows(group)
        by_policy = {r["policy"]: r for r in group}
        reference, candidate, heuristic = (by_policy[p] for p in
                                            (REFERENCE, CANDIDATE, HEURISTIC))
        task_subset = [r for r in completed_rows if int(r["seed"]) == seed]
        pair = compare_task_rows(task_subset, reference=REFERENCE)
        if {r["policy"] for r in pair} != {CANDIDATE, HEURISTIC}:
            raise AssertionError("missing task-level comparator")
        by_pair = {r["policy"]: r for r in pair}
        action = by_pair[CANDIDATE]
        if action["paired_completed_tasks"] != int(reference["tasks_finished"]):
            raise AssertionError("task-level cohort and run summary disagree")
        sla_delta = int(candidate["sla_violated"]) - int(reference["sla_violated"])
        if sla_delta != action["sla_harmed"] - action["sla_rescued"]:
            raise AssertionError("paired SLA transitions do not reconcile")
        if int(candidate["nsga2_evaluation_requests"]) != int(
                reference["nsga2_evaluation_requests"]):
            raise AssertionError("mismatched GA budget")
        steps = int(candidate["steps_completed"])
        if steps <= 0 or int(candidate["lagged_pue_observation_steps"]) != steps:
            raise AssertionError("missing past-step facility observations")
        missing = int(candidate["lagged_pue_missing_site_readings"])
        nonunit = int(candidate["lagged_pue_nonunit_site_readings"])
        if (min(missing, nonunit) < 0 or missing + nonunit > 5 * steps):
            raise AssertionError("invalid PUE coverage counters")
        maximum = _finite(candidate, "lagged_pue_max")
        if not 1.0 <= maximum <= 3.0:
            raise AssertionError("PUE outside predeclared clipping interval")
        for row in group:
            for stem, total, parts in (
                ("carbon", "reported_total_carbon_kg",
                 ("facility_carbon_kg", "transmission_carbon_kg")),
                ("cost", "reported_total_cost_usd",
                 ("facility_cost_usd", "transmission_cost_usd")),
            ):
                if not math.isclose(
                    _finite(row, total),
                    sum(_finite(row, name) for name in parts),
                    rel_tol=1e-8, abs_tol=1e-5,
                ):
                    raise AssertionError(f"incorrect {stem} aggregation")
        carbon_delta = (_finite(candidate, "reported_total_carbon_kg")
                        - _finite(reference, "reported_total_carbon_kg"))
        cost_delta = (_finite(candidate, "reported_total_cost_usd")
                      - _finite(reference, "reported_total_cost_usd"))
        out.append({
            "month": month, "day": day, "cpu_capacity_scale": scale,
            "seed": seed,
            "tasks_per_policy": int(reference["tasks_finished"]),
            "ga_requests": int(candidate["nsga2_evaluation_requests"]),
            "pue_nonunit_site_observations": nonunit,
            "pue_missing_site_observations": missing,
            "pue_max": maximum,
            "route_changes": action["destination_changes"],
            "sla_rescued": action["sla_rescued"],
            "sla_harmed": action["sla_harmed"],
            "control_sla_misses": int(reference["sla_violated"]),
            "candidate_sla_misses": int(candidate["sla_violated"]),
            "heuristic_sla_misses": int(heuristic["sla_violated"]),
            "sla_misses_delta": sla_delta,
            "control_realized_carbon_kg": _finite(reference, "reported_total_carbon_kg"),
            "candidate_realized_carbon_kg": _finite(candidate, "reported_total_carbon_kg"),
            "heuristic_realized_carbon_kg": _finite(heuristic, "reported_total_carbon_kg"),
            "realized_carbon_delta_kg": carbon_delta,
            "realized_cost_delta_usd": cost_delta,
            "planner_p95_delta_ms": (
                _finite(candidate, "planner_dispatch_p95_ms")
                - _finite(reference, "planner_dispatch_p95_ms")),
            "joint_carbon_and_sla_nonworse": carbon_delta <= 0 and sla_delta <= 0,
            "complete_matched_cohort": True,
        })
    if len(out) != 2:
        raise AssertionError("missing paired seed")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--tasks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    runs = json.loads(args.runs.read_text(encoding="utf8"))
    with args.tasks.open(newline="", encoding="utf8") as f:
        rows = list(csv.DictReader(f))
    report = audit_prospective(runs, rows)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                           encoding="utf8")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
