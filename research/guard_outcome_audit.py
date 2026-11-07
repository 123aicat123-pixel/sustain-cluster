"""Scenario-level audit of proxy carbon guards against real SLA outcomes.

Audit each (calendar, seed) as a paired *simulation scenario*. Task counts are
NOT independent replicates. Negative findings are retained instead of failing CI.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def audit_guard_runs(rows, *, guard="queue_nsga2_carbon_sla_guard",
                     reference="queue_nsga2"):
    by_seed = {}
    for row in rows:
        key = (str(row["seed"]), str(row["policy"]))
        if key in by_seed:
            raise ValueError(f"duplicate run: {key}")
        by_seed[key] = row
    seeds = sorted({seed for seed, _ in by_seed})
    report = []
    for seed in seeds:
        if (seed, guard) not in by_seed or (seed, reference) not in by_seed:
            raise ValueError(f"missing guard or reference for seed {seed}")
        g, b = by_seed[(seed, guard)], by_seed[(seed, reference)]
        if int(g["tasks_dispatched"]) != int(b["tasks_dispatched"]):
            raise ValueError(f"unequal admission task counts for seed {seed}")
        eligible = all(
            int(row["unfinished_dispatched"]) == 0
            and int(row["fallback_assignments"]) == 0
            and bool(row["lifecycle_conserved"])
            for row in (g, b)
        )
        if not eligible:
            report.append({"seed": seed, "eligible": False,
                           "reason": "unfinished/fallback/lifecycle discrepancy"})
            continue
        for row in (g, b):
            if int(row["tasks_finished"]) != int(row["tasks_dispatched"]):
                raise ValueError("finished count inconsistent with full drain")
            if int(row["sla_met"]) + int(row["sla_violated"]) != int(row["tasks_finished"]):
                raise ValueError("invalid SLA accounting")
        delta_sla = int(g["sla_violated"]) - int(b["sla_violated"])
        delta_carbon = float(g["reported_total_carbon_kg"]) - float(b["reported_total_carbon_kg"])
        delta_cost = float(g["reported_total_cost_usd"]) - float(b["reported_total_cost_usd"])
        report.append({
            "seed": seed, "eligible": True,
            "tasks": int(g["tasks_finished"]),
            "guard_interventions": int(g.get("carbon_guard_interventions", 0)),
            "guard_risk_vetoes": int(g.get("carbon_guard_vetoes", 0)),
            "guard_minus_reference_sla_misses": delta_sla,
            "guard_minus_reference_carbon_kg": delta_carbon,
            "guard_minus_reference_cost_usd": delta_cost,
            "observed_no_extra_sla_misses": delta_sla <= 0,
            "observed_nonincreasing_carbon": delta_carbon <= 0,
            "observed_three_objective_weak_dominance":
                delta_sla <= 0 and delta_carbon <= 0 and delta_cost <= 0,
        })
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--guard", default="queue_nsga2_carbon_sla_guard")
    p.add_argument("--reference", default="queue_nsga2")
    args = p.parse_args()
    report = audit_guard_runs(json.loads(args.input.read_text()),
                              guard=args.guard, reference=args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("No algorithmic safety guarantee: flags describe simulator outcomes only.")
    print("Scenario seeds within the same calendar trace are correlated.")


if __name__ == "__main__":
    main()
