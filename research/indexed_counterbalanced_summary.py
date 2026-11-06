"""Summarize counterbalanced indexed-queue experiments without cherry-picking.

Order-level results remain visible. Both order directions must be present.
No hypothesis test or independence assumption is made for random seeds that
share the same Alibaba arrival calendar date.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


METRICS = ("p95_delta_ms", "per_task_delta_ms", "projection_delta_seconds")


def summarize_counterbalanced(reports):
    """Input mapping scenario_name -> result records from indexed_order_audit."""
    if not reports:
        raise ValueError("at least one scenario required")
    scenarios = []
    for name, records in sorted(reports.items()):
        if not isinstance(name, str) or not name.strip() or not records:
            raise ValueError("empty scenario label or records")
        seen_seeds = set()
        entries = []
        for record in records:
            seed = int(record["seed"])
            if seed in seen_seeds:
                raise AssertionError("duplicate seed within scenario")
            seen_seeds.add(seed)
            if record.get("exact_task_level_equality") is not True:
                raise AssertionError("counterbalanced task equality not verified")
            n = int(record["tasks_per_policy"])
            if n <= 0:
                raise AssertionError("empty paired task cohort")
            orders = record["orders"]
            if set(orders) != {"forward", "reverse"}:
                raise AssertionError("both run orders required")
            for order in ("forward", "reverse"):
                v = orders[order]
                for metric in METRICS:
                    if not math.isfinite(float(v[metric])):
                        raise AssertionError("non-finite timing metric")
                legacy = float(v["legacy_p95_ms"])
                indexed = float(v["indexed_p95_ms"])
                if not all(math.isfinite(x) and x >= 0 for x in (legacy, indexed)):
                    raise AssertionError("negative or nonfinite absolute P95")
                if not math.isclose(indexed - legacy, float(v["p95_delta_ms"]),
                                    rel_tol=1e-9, abs_tol=1e-7):
                    raise AssertionError("P95 signed delta contradicts absolute times")
            means = {metric: sum(float(orders[order][metric])
                     for order in ("forward", "reverse")) / 2
                     for metric in METRICS}
            def direction(metric):
                a, z = (float(orders[order][metric])
                        for order in ("forward", "reverse"))
                if a < 0 and z < 0:
                    return "faster_both_orders"
                if a > 0 and z > 0:
                    return "slower_both_orders"
                if a == 0 and z == 0:
                    return "equal_both_orders"
                return "mixed_or_zero"
            entries.append({
                "seed": seed, "tasks_per_policy": n,
                "forward": {m: float(orders["forward"][m]) for m in METRICS},
                "reverse": {m: float(orders["reverse"][m]) for m in METRICS},
                "order_mean": means,
                "p95_direction": direction("p95_delta_ms"),
                "per_task_direction": direction("per_task_delta_ms"),
            })
        scenarios.append({
            "scenario": name, "number_of_seeds": len(entries),
            "seed_results": sorted(entries, key=lambda x: x["seed"]),
        })
    return {
        "interpretation": (
            "descriptive only: paired seeds share workload dates; "
            "no p-value, confidence interval or universal speedup claim"
        ),
        "number_of_scenarios": len(scenarios),
        "scenarios": scenarios,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inputs", nargs="+", type=Path, required=True,
                   help="One *_audit.json file per distinct scenario")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    reports = {}
    for path in args.inputs:
        label = path.stem.removesuffix("_audit")
        if label in reports:
            raise ValueError(f"duplicate scenario label {label}")
        reports[label] = json.loads(path.read_text(encoding="utf8"))
    result = summarize_counterbalanced(reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                           encoding="utf8")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
