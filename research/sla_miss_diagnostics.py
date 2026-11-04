"""Post-hoc diagnosis of task-level SLA forecast failures.

Inputs are previously archived task-start forecast observations, NOT an
online feature pipeline. NEVER use the resulting realized-error quantiles
or the best-performing buffer on the same trace to claim an out-of-sample
scheduler improvement. Calibrate on prior trace dates and test on unseen dates.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean


BUFFERS_MINUTES = (0, 15, 30, 60, 120)


def flag(value):
    if value in (True, "True", "true", "1", 1):
        return True
    if value in (False, "False", "false", "0", 0):
        return False
    raise ValueError(f"invalid Boolean CSV value: {value!r}")


def slack_band(slack):
    if slack < 0:
        return "predicted_late"
    if slack < 15:
        return "pred_safe_0_to_15m"
    if slack < 30:
        return "pred_safe_15_to_30m"
    if slack < 60:
        return "pred_safe_30_to_60m"
    return "pred_safe_60m_plus"


def percentile_nearest_rank(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * pct) - 1)]


def summarize(group):
    n = len(group)
    if n == 0:
        return {"count": 0, "actual_misses": 0, "false_safe": 0,
                "false_alarm": 0, "start_mae_min": None,
                "positive_start_error_p95_min": None}
    false_safe = sum(r["predicted_met"] and not r["actual_met"] for r in group)
    false_alarm = sum(not r["predicted_met"] and r["actual_met"] for r in group)
    positive_errors = [max(0.0, r["residual"]) for r in group]
    return {
        "count": n,
        "actual_misses": sum(not r["actual_met"] for r in group),
        "false_safe": false_safe,
        "false_alarm": false_alarm,
        "start_mae_min": mean(abs(r["residual"]) for r in group),
        "positive_start_error_p95_min": percentile_nearest_rank(positive_errors, .95),
    }


def analyze(rows, buffers=BUFFERS_MINUTES):
    parsed = []
    for record in rows:
        slack = float(record["predicted_slack_minutes"])
        residual = float(record["residual_actual_minus_prediction_minutes"])
        if not math.isfinite(slack) or not math.isfinite(residual):
            raise ValueError("nonfinite slack or residual")
        pred = flag(record["predicted_sla_met"])
        actual = flag(record["actual_sla_met"])
        if pred != (slack >= -1e-9):
            raise AssertionError("predicted SLA status inconsistent with slack")
        if "false_safe" in record and flag(record["false_safe"]) != (pred and not actual):
            raise AssertionError("false-safe flag inconsistent")
        parsed.append({
            "policy": record["policy"], "remote": flag(record["is_remote"]),
            "predicted_met": pred, "actual_met": actual,
            "slack": slack, "residual": residual,
        })
    policies = sorted({r["policy"] for r in parsed})
    result = {}
    for policy in policies:
        cohort = [r for r in parsed if r["policy"] == policy]
        groups = {
            "all": cohort,
            "local": [r for r in cohort if not r["remote"]],
            "remote": [r for r in cohort if r["remote"]],
        }
        for band in ("predicted_late", "pred_safe_0_to_15m",
                     "pred_safe_15_to_30m", "pred_safe_30_to_60m",
                     "pred_safe_60m_plus"):
            groups[band] = [r for r in cohort if slack_band(r["slack"]) == band]
        report = {key: summarize(group) for key, group in groups.items()}
        assert report["local"]["count"]+report["remote"]["count"] == len(cohort)
        assert sum(report[b]["count"] for b in (
            "predicted_late", "pred_safe_0_to_15m",
            "pred_safe_15_to_30m", "pred_safe_30_to_60m",
            "pred_safe_60m_plus")) == len(cohort)
        sweeps = []
        for buffer in buffers:
            if not math.isfinite(buffer) or buffer < 0:
                raise ValueError("invalid buffer")
            # Post-hoc diagnostic classifier only: NOT real scheduling.
            predictions = [r["slack"] >= buffer for r in cohort]
            actual_miss = sum(not r["actual_met"] for r in cohort)
            false_safe = sum(pred and not r["actual_met"]
                             for pred, r in zip(predictions, cohort))
            false_alarm = sum(not pred and r["actual_met"]
                              for pred, r in zip(predictions, cohort))
            sweeps.append({
                "buffer_minutes": buffer,
                "predicted_safe": sum(predictions),
                "false_safe": false_safe,
                "false_alarm": false_alarm,
                "actual_misses_unchanged": actual_miss,
            })
        result[policy] = {
            "grouped": report,
            "retrospective_buffer_classification_only": sweeps,
        }
    return {
        "policy_results": result,
        "warning": (
            "The buffer sweep is a retrospective classifier, not an actual "
            "rescheduling experiment or validated safety guarantee. "
            "Do not optimize buffer on this test cohort."
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    with args.input.open(newline="", encoding="utf8") as f:
        result = analyze(list(csv.DictReader(f)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf8")
    for policy, report in result["policy_results"].items():
        print(policy, json.dumps(report, sort_keys=True))
    print(result["warning"])


if __name__ == "__main__":
    main()
