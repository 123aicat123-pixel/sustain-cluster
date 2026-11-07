"""Paired task-level route-change / queue-spillover diagnostic.

This retrospective diagnostic is *observational*: SLA changes among tasks
whose destination did not change can indicate shared-queue interactions,
but do NOT identify a causal effect without controlled interventions.

A source experiment must already have finished every task and passed a
separate run-level lifecycle and carbon conservation audit.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

IMMUTABLE = ("duration_minutes", "deadline_utc", "origin_dc_id")


def strict_bool(value):
    if value is True or str(value).strip().lower() == "true":
        return True
    if value is False or str(value).strip().lower() == "false":
        return False
    raise ValueError(f"invalid task SLA status: {value!r}")


def _index(rows, policy, seed):
    index = {}
    for row in rows:
        if str(row["policy"]) != policy or str(row["seed"]) != str(seed):
            continue
        key = (row["arrival_utc"], row["job_name"])
        if key in index:
            raise AssertionError(f"duplicate task key: {policy}, {seed}, {key}")
        index[key] = row
    if not index:
        raise AssertionError(f"empty task group: {policy}, seed={seed}")
    return index


def audit_route_spillover(rows, reference, candidates, seeds=(901, 1701)):
    if not reference or not candidates or len(set(candidates)) != len(candidates):
        raise ValueError("reference and distinct candidates required")
    if reference in candidates:
        raise ValueError("reference cannot be its own candidate")
    observed = defaultdict(set)
    requested = {reference, *candidates}
    for row in rows:
        if row["policy"] in requested:
            observed[row["policy"]].add(str(row["seed"]))
    expected_seeds = {str(s) for s in seeds}
    if set(observed) != requested or any(v != expected_seeds for v in observed.values()):
        raise AssertionError("missing or unexpected policy/seed task cohort")
    results = []
    for seed in seeds:
        baseline = _index(rows, reference, seed)
        for candidate in candidates:
            other = _index(rows, candidate, seed)
            if baseline.keys() != other.keys():
                raise AssertionError("unequal admission cohort")
            breakdown = {
                "route_changed": {"tasks": 0, "sla_rescued": 0,
                                  "sla_harmed": 0, "start_changed": 0,
                                  "finish_changed": 0},
                "route_unchanged": {"tasks": 0, "sla_rescued": 0,
                                    "sla_harmed": 0, "start_changed": 0,
                                    "finish_changed": 0}
            }
            for key, base in baseline.items():
                trial = other[key]
                if any(base[k] != trial[k] for k in IMMUTABLE):
                    raise AssertionError(f"immutable task fields changed: {key}")
                status0, status1 = strict_bool(base["sla_met"]), strict_bool(trial["sla_met"])
                label = ("route_changed" if base["dest_dc_id"] != trial["dest_dc_id"]
                         else "route_unchanged")
                slot = breakdown[label]
                slot["tasks"] += 1
                slot["sla_rescued"] += int(not status0 and status1)
                slot["sla_harmed"] += int(status0 and not status1)
                slot["start_changed"] += int(base["start_utc"] != trial["start_utc"])
                slot["finish_changed"] += int(base["finish_utc"] != trial["finish_utc"])
            if sum(x["tasks"] for x in breakdown.values()) != len(baseline):
                raise AssertionError("task partition does not conserve cohort")
            results.append({
                "reference": reference, "candidate": candidate,
                "seed": int(seed), "completed_matched_tasks": len(baseline),
                "route_change_partitions": breakdown,
                "all_sla_rescued": sum(x["sla_rescued"] for x in breakdown.values()),
                "all_sla_harmed": sum(x["sla_harmed"] for x in breakdown.values()),
                "sla_miss_delta": sum(
                    x["sla_harmed"] - x["sla_rescued"]
                    for x in breakdown.values()
                ),
                "unchanged_route_sla_transitions_not_causal_proof": True
            })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", required=True, type=Path)
    parser.add_argument("--reference", default="queue_nsga2_indexed_transit")
    parser.add_argument("--candidates", required=True, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with args.tasks.open(newline="", encoding="utf8") as fp:
        rows = list(csv.DictReader(fp))
    report = audit_route_spillover(rows, args.reference, args.candidates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf8"
    )
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
