"""Paired, task-level comparison for common-admission SustainCluster runs.

Requires the raw per-task audit CSV produced by batch_unified_baselines.
Matches by seed + arrival timestamp + job name, verifies each policy received
the SAME tasks, then counts SLA rescues, harms, destination/finish differences.

This is descriptive evidence only: tasks within a seed are correlated; do not
treat 776 jobs as independent experimental replications or attach a naive
per-task p-value to the result. Use multiple independent workload scenarios.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compare_task_rows(rows, reference="lowest_carbon"):
    cohorts = defaultdict(dict)
    for row in rows:
        policy = row["policy"]
        seed = str(row["seed"])
        key = (row["arrival_utc"], row["job_name"])
        cell = cohorts[(seed, policy)]
        if key in cell:
            raise AssertionError(f"Duplicate task key in seed {seed} policy {policy}: {key}")
        cell[key] = row

    seeds = sorted({seed for seed, policy in cohorts})
    policies = sorted({policy for seed, policy in cohorts})
    results = []
    for seed in seeds:
        if (seed, reference) not in cohorts:
            raise AssertionError(f"Reference {reference} missing for seed {seed}")
        base = cohorts[(seed, reference)]
        for policy in policies:
            if policy == reference:
                continue
            key = (seed, policy)
            if key not in cohorts:
                raise AssertionError(f"Policy {policy} missing for seed {seed}")
            candidate = cohorts[key]
            if base.keys() != candidate.keys():
                raise AssertionError(
                    f"Unequal admission/cohort for {policy} seed {seed}: "
                    f"missing={len(base.keys()-candidate.keys())}, "
                    f"extra={len(candidate.keys()-base.keys())}"
                )
            rescued = harmed = stayed_violated = stayed_met = 0
            route_changes = start_changes = finish_changes = 0
            for taskkey in base:
                before, after = base[taskkey], candidate[taskkey]
                b_met = str(before["sla_met"]).lower() == "true"
                a_met = str(after["sla_met"]).lower() == "true"
                rescued += int((not b_met) and a_met)
                harmed += int(b_met and (not a_met))
                stayed_violated += int((not b_met) and (not a_met))
                stayed_met += int(b_met and a_met)
                # Assert immutable task characteristics to catch silent trace drift.
                for immutable in ("duration_minutes", "deadline_utc", "origin_dc_id"):
                    if before[immutable] != after[immutable]:
                        raise AssertionError(f"Mismatched task {taskkey}: {immutable}")
                route_changes += before["dest_dc_id"] != after["dest_dc_id"]
                start_changes += before["start_utc"] != after["start_utc"]
                finish_changes += before["finish_utc"] != after["finish_utc"]
            results.append({
                "seed": seed, "reference": reference, "policy": policy,
                "paired_completed_tasks": len(base),
                "sla_rescued": rescued, "sla_harmed": harmed,
                "both_violated": stayed_violated, "both_met": stayed_met,
                "destination_changes": route_changes,
                "start_time_changes": start_changes,
                "finish_time_changes": finish_changes,
            })
            if rescued + harmed + stayed_violated + stayed_met != len(base):
                raise AssertionError("Pair table does not conserve task count")
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=ROOT / "research/results/unified_batch_completed_tasks.csv")
    p.add_argument("--reference", default="lowest_carbon")
    p.add_argument("--output", type=Path, default=ROOT / "research/results/paired_task_audit.json")
    args = p.parse_args()
    with args.input.open(newline="", encoding="utf8") as f:
        rows = list(csv.DictReader(f))
    result = compare_task_rows(rows, reference=args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps(result, indent=2))
    print("CAUTION: paired task counts are descriptive, not independent significance tests.")


if __name__ == "__main__":
    main()
