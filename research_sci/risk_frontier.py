"""Predeclared frozen-risk buffer sweep on chronological held-out tasks.

The PRIMARY comparison is per-seed paired, with matched calibration and test
admissions. We report real deadline misses/unfinished work and facility+network
CO2, and NEVER interpret an empty 'predicted safe' group as zero SLA risk.

No hyperparameter is selected using these held-out outcomes. In particular
the displayed Pareto points are descriptive only, NOT a tuned deployed policy
and NOT evidence of statistical significance.
"""
import argparse
import csv
import json
import math
from pathlib import Path

from research_sci.chronological_eval import (
    ROOT, TREATMENTS, run_one, frozen_buffer_for_treatment,
)


def validate_paired(rows):
    if not rows:
        raise ValueError("No evaluation rows")
    seeds = sorted({int(row["seed"]) for row in rows})
    treatments = set(TREATMENTS)
    groups = {}
    for row in rows:
        key = (row["seed"], row["treatment"])
        if key in groups:
            raise ValueError("Duplicated seed/treatment")
        if row["treatment"] not in treatments:
            raise ValueError("Unexpected treatment")
        groups[key] = row
    for seed in seeds:
        observed = {t for (s, t) in groups if s == seed}
        if observed != treatments:
            raise ValueError(f"Incomplete paired treatments for seed {seed}: {observed}")
        reference = groups[(seed, "fixed_30")]
        for treatment in treatments:
            row = groups[(seed, treatment)]
            for field in (
                "train_window_start", "train_admissions_end",
                "test_window_start", "test_admissions_end",
                "pretest_train_completed", "pretest_train_forecast_residuals",
                "pretest_learned_buffer_minutes", "train_routing_signature",
                "train_admission_signature", "test_admission_signature",
                "test_tasks_admitted", "capacity_scale",
                "calibration_steps", "gap_steps", "test_steps", "drain_steps",
            ):
                if row[field] != reference[field]:
                    raise AssertionError(f"Unmatched {field} for seed {seed}")
            actual_margin = row["applied_frozen_buffer_minutes"]
            expected = frozen_buffer_for_treatment(
                treatment, row["pretest_learned_buffer_minutes"])
            if not math.isclose(actual_margin, expected, abs_tol=1e-6):
                raise AssertionError("Frozen buffer mismatch")
            if row["test_tasks_finished"] + row["test_unfinished"] != row["test_tasks_admitted"]:
                raise AssertionError("Task lifecycle not conserved")
            if row["test_sla_met"] + row["test_sla_violated"] != row["test_tasks_finished"]:
                raise AssertionError("SLA completion conservation failure")
            if row["test_unfinished_overdue"] > row["test_unfinished"]:
                raise AssertionError("Overdue unfinished exceeds all unfinished")
            if row["test_safe_flag_is_vacuous"] != (
                    row["test_decision_margin_predicted_safe_completed"] == 0):
                raise AssertionError("Vacuous-safe diagnostic inconsistent")
    return groups


def summarize_frontier(rows):
    groups = validate_paired(rows)
    seed_list = sorted({int(r["seed"]) for r in rows})
    output = {
        "design": "predeclared_frozen_buffers_30_60_120_and_train_quantile",
        "seeds": seed_list,
        "warning": (
            "Descriptive pilot. 2 seeds, synthetic 2%-capacity, test-window "
            "outcomes are not used for margin selection. Actual coverage is "
            "completed-task-only and NO formal probability guarantee applies."
        ),
        "treatments": [],
    }
    for treatment in TREATMENTS:
        rs = [groups[(seed, treatment)] for seed in seed_list]
        baseline = [groups[(seed, "fixed_30")] for seed in seed_list]
        equal_completed = all(
            a["test_tasks_finished"] == b["test_tasks_finished"]
            for a, b in zip(rs, baseline)
        )
        count = len(rs)
        safe = sum(r["test_decision_margin_predicted_safe_completed"] for r in rs)
        false_safe = sum(r["test_decision_margin_false_safe_completed"] for r in rs)
        admitted = sum(r["test_tasks_admitted"] for r in rs)
        completed = sum(r["test_tasks_finished"] for r in rs)
        mean_carbon = sum(r["test_total_carbon_kg"] for r in rs) / count
        mean_misses = sum(r["test_deadline_failures_including_overdue"] for r in rs) / count
        entry = {
            "treatment": treatment,
            "mean_buffer_minutes": sum(r["applied_frozen_buffer_minutes"] for r in rs) / count,
            "mean_carbon_kg": mean_carbon,
            "mean_deadline_failures": mean_misses,
            "mean_finished": completed / count,
            "mean_unfinished": sum(r["test_unfinished"] for r in rs) / count,
            "mean_overdue_unfinished": sum(r["test_unfinished_overdue"] for r in rs) / count,
            "pooled_actual_deadline_failure_rate_admitted": (
                sum(r["test_deadline_failures_including_overdue"] for r in rs) / admitted
            ),
            "pooled_safe_prediction_fraction_admitted": safe / admitted,
            "pooled_false_safe_rate_if_defined": (false_safe / safe if safe else None),
            "has_nonvacuous_safe_predictions": safe > 0,
            "equal_completed_work_to_fixed_30": equal_completed,
            "per_seed": [{
                "seed": row["seed"],
                "carbon_kg": row["test_total_carbon_kg"],
                "finished": row["test_tasks_finished"],
                "deadline_failures": row["test_deadline_failures_including_overdue"],
                "safe_flag_count": row["test_decision_margin_predicted_safe_completed"],
                "frozen_buffer": row["applied_frozen_buffer_minutes"],
            } for row in rs],
        }
        output["treatments"].append(entry)
    # Purely descriptive dominance, only within the set of compared policies.
    # Do not compare different completed-work totals as equivalent.
    for x in output["treatments"]:
        if not x["equal_completed_work_to_fixed_30"]:
            x["descriptive_pareto_nondominated"] = None
            continue
        x["descriptive_pareto_nondominated"] = not any(
            y is not x and y["equal_completed_work_to_fixed_30"]
            and y["mean_carbon_kg"] <= x["mean_carbon_kg"]
            and y["mean_deadline_failures"] <= x["mean_deadline_failures"]
            and (
                y["mean_carbon_kg"] < x["mean_carbon_kg"]
                or y["mean_deadline_failures"] < x["mean_deadline_failures"]
            )
            for y in output["treatments"]
        )
    return output


def run_sweep(seeds, output, **kwargs):
    if len(set(seeds)) != len(seeds) or not seeds:
        raise ValueError("Require unique seeds")
    rows = []
    for seed in seeds:
        for treatment in TREATMENTS:
            result, routes = run_one(seed, treatment, **kwargs)
            rows.append(result)
            print(json.dumps({
                "seed": seed, "treatment": treatment,
                "margin": result["applied_frozen_buffer_minutes"],
                "carbon_kg": result["test_total_carbon_kg"],
                "sla_failures": result["test_deadline_failures_including_overdue"],
                "finished": result["test_tasks_finished"],
                "safe_count": result["test_decision_margin_predicted_safe_completed"],
                "true_failure_rate": result["test_deadline_failure_rate_admitted"],
            }), flush=True)
    summary = summarize_frontier(rows)
    output = Path(output)
    output.parent.mkdir(exist_ok=True, parents=True)
    output.write_text(json.dumps(rows, indent=2, allow_nan=False), encoding="utf-8")
    summary_path = output.with_name(output.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    with output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2, allow_nan=False), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 42])
    parser.add_argument("--calibration-steps", type=int, default=16)
    parser.add_argument("--gap-steps", type=int, default=128)
    parser.add_argument("--test-steps", type=int, default=16)
    parser.add_argument("--drain-steps", type=int, default=96)
    parser.add_argument("--capacity-scale", type=float, default=.02)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "research_sci/results/risk_frontier.json")
    args = parser.parse_args()
    run_sweep(args.seeds, args.output,
              calibration_steps=args.calibration_steps,
              gap_steps=args.gap_steps,
              test_steps=args.test_steps,
              drain_steps=args.drain_steps,
              capacity_scale=args.capacity_scale)


if __name__ == "__main__":
    main()
