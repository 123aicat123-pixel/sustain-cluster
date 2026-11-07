"""Decompose observed carbon/cost changes by facility and transmission.

Pure post-processing of *simulator-reported* data, not a physics model.
Requires matched fully-drained cohorts and no fallback to provide a paired
difference; otherwise records eligibility errors and refuses rankings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, stdev


COMPONENTS = (
    "facility_cost_usd",
    "transmission_cost_usd",
    "facility_carbon_kg",
    "transmission_carbon_kg",
    "remote_dispatches",
    "local_dispatches",
    "sla_violated",
)
COST_KEYS = ("facility_cost_usd", "transmission_cost_usd")
CARBON_KEYS = ("facility_carbon_kg", "transmission_carbon_kg")


def analyze(rows, reference="queue_nsga2_no_queue"):
    cohorts = {}
    for item in rows:
        key = (int(item["seed"]), item["policy"])
        if key in cohorts:
            raise ValueError(f"repeated seed/policy: {key}")
        cohorts[key] = item
    seeds = sorted({seed for seed, _ in cohorts})
    policies = sorted({policy for _, policy in cohorts})
    if reference not in policies:
        raise ValueError(f"missing reference policy {reference}")
    results = []
    for seed in seeds:
        base = cohorts.get((seed, reference))
        if base is None:
            raise ValueError(f"seed {seed} lacks reference {reference}")
        for policy in policies:
            target = cohorts.get((seed, policy))
            if target is None:
                raise ValueError(f"seed {seed} lacks policy {policy}")
            eligible = (
                base["fully_drained"]
                and target["fully_drained"]
                and base["fallback_assignments"] == 0
                and target["fallback_assignments"] == 0
                and base["tasks_dispatched"] == target["tasks_dispatched"]
                and base["tasks_finished"] == target["tasks_finished"]
            )
            if not eligible:
                results.append({
                    "seed": seed, "policy": policy, "reference": reference,
                    "eligible": False,
                    "reason": "censored, fallback or unequal cohort size",
                })
                continue
            delta = {
                name: (float(target[name]) - float(base[name]))
                for name in COMPONENTS
            }
            for key, fields in (
                ("cost", COST_KEYS),
                ("carbon", CARBON_KEYS),
            ):
                expected = sum(delta[k] for k in fields)
                reported = (
                    float(target[f"reported_total_{key}_usd" if key == "cost" else "reported_total_carbon_kg"])
                    - float(base[f"reported_total_{key}_usd" if key == "cost" else "reported_total_carbon_kg"])
                )
                if abs(expected - reported) > 1e-5:
                    raise AssertionError(
                        f"{key} breakdown does not reconcile: {expected}, {reported}"
                    )
            results.append({
                "seed": seed, "policy": policy, "reference": reference,
                "eligible": True,
                "delta": delta,
                "delta_total_carbon_kg": (
                    delta["facility_carbon_kg"] + delta["transmission_carbon_kg"]
                ),
                "delta_total_cost_usd": (
                    delta["facility_cost_usd"] + delta["transmission_cost_usd"]
                ),
            })
    full = {
        "reference": reference,
        "results": results,
        "unusable": [r for r in results if not r["eligible"]],
        "mean_deltas": {},
    }
    for policy in policies:
        chosen = [r for r in results if r["policy"] == policy and r["eligible"]]
        if len(chosen) != len(seeds):
            full["mean_deltas"][policy] = None
            continue
        values = {key: [r["delta"][key] for r in chosen] for key in COMPONENTS}
        full["mean_deltas"][policy] = {
            key: {
                "mean": mean(x), "sd": stdev(x) if len(x) > 1 else None,
                "signs": [0 if abs(value) < 1e-9 else (1 if value > 0 else -1) for value in x],
            }
            for key, x in values.items()
        }
    return full


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--reference", default="queue_nsga2_no_queue")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    data = analyze(json.loads(args.input.read_text(encoding="utf8")),
                   reference=args.reference)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2), encoding="utf8")
    print(json.dumps(data, indent=2))
    if data["unusable"]:
        print("CENSORED: Some runs are unfit for paired full-cohort comparisons.")
    else:
        print("All runs eligible for DESCRIPTIVE seed-paired decomposition; no significance claim.")


if __name__ == "__main__":
    main()
