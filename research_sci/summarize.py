"""Summarize paired exploratory pilot results without hiding unfinished tasks.

No statistical superiority claim is made: paired seed counts may be small,
and horizon-based emissions must be interpreted with unequal completion.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def summarize(rows, reference="round_robin"):
    grouped = defaultdict(dict)
    for row in rows:
        seed = row["seed"]
        policy = row["policy"]
        if policy in grouped[seed]:
            raise ValueError(f"Repeated seed/policy: {seed}/{policy}")
        grouped[seed][policy] = row
    if not grouped:
        raise ValueError("No experimental rows")
    policies = set(next(iter(grouped.values())))
    if reference not in policies:
        raise ValueError(f"Missing reference policy {reference}")
    for seed, group in grouped.items():
        if set(group) != policies:
            raise ValueError(f"Missing policies for seed {seed}")
        arrivals = {r["tasks_dispatched"] for r in group.values()}
        if len(arrivals) != 1:
            raise ValueError(f"Unequal task admissions for seed {seed}: {sorted(arrivals)}")
    out = {
        "reference": reference,
        "seeds": sorted(grouped),
        "warning": "Exploratory results only. Small seed count, incomplete tasks, and short traces prevent SCI claims.",
        "policies": {},
    }
    for policy in sorted(policies):
        values = [grouped[seed][policy] for seed in sorted(grouped)]
        refs = [grouped[seed][reference] for seed in sorted(grouped)]
        carbon = [float(row["total_reported_carbon_kg"]) for row in values]
        unfinished = [int(row["unfinished_at_horizon"]) for row in values]
        overdue = [int(row["unfinished_overdue"]) for row in values]
        completed = [int(row["tasks_finished"]) for row in values]
        relative = [
            100.0 * (a / float(ref["total_reported_carbon_kg"]) - 1)
            for a, ref in zip(carbon, refs)
        ]
        if not all(math.isfinite(v) for v in relative):
            raise ValueError("Non-finite paired carbon difference")
        out["policies"][policy] = {
            "mean_carbon_kg": sum(carbon) / len(carbon),
            "mean_paired_carbon_delta_pct": sum(relative) / len(relative),
            "per_seed_paired_carbon_delta_pct": relative,
            "mean_finished": sum(completed) / len(completed),
            "mean_unfinished": sum(unfinished) / len(unfinished),
            "mean_unfinished_overdue": sum(overdue) / len(overdue),
            "comparison_not_fair_if_unequal_completed": any(
                a != b["tasks_finished"] for a, b in zip(completed, refs)
            ),
        }
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="run_pilot JSON file")
    parser.add_argument("--reference", default="round_robin")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    results = summarize(json.loads(args.input.read_text(encoding="utf-8")), reference=args.reference)
    output = args.output or args.input.with_name(args.input.stem + "_summary.json")
    output.write_text(json.dumps(results, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
