"""Retrospective, scenario-separated queue forecast risk audit.

No realized label can be used as an online scheduler feature. Rates describe
these completed cohorts only; a new calendar partition is required to test
any threshold learned from them.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from research.sla_miss_diagnostics import flag, slack_band


def scenario_risk_table(rows):
    groups = defaultdict(list)
    identities = set()
    for row in rows:
        month = str(row.get("scenario_start_month", "unspecified"))
        day = str(row.get("scenario_start_day", "unspecified"))
        seed = str(row["seed"])
        policy = str(row["policy"])
        taskkey = (month, day, seed, policy, str(row["arrival_utc"]),
                   str(row["job_name"]))
        if taskkey in identities:
            raise AssertionError(f"duplicate task forecast: {taskkey}")
        identities.add(taskkey)
        slack = float(row["predicted_slack_minutes"])
        residual = float(row["residual_actual_minus_prediction_minutes"])
        if not math.isfinite(slack) or not math.isfinite(residual):
            raise ValueError("nonfinite risk audit input")
        pred = flag(row["predicted_sla_met"])
        actual = flag(row["actual_sla_met"])
        if pred != (slack >= -1e-9):
            raise AssertionError("predicted SLA/slack mismatch")
        if "false_safe" in row and flag(row["false_safe"]) != (pred and not actual):
            raise AssertionError("false-safe label mismatch")
        remote = flag(row["is_remote"])
        groups[(month, day, seed, policy)].append(
            {"slack": slack, "residual": residual, "pred": pred,
             "actual": actual, "remote": remote}
        )

    report = []
    for (month, day, seed, policy), tasks in sorted(groups.items()):
        predicted_safe = [r for r in tasks if r["pred"]]
        false_safe = [r for r in predicted_safe if not r["actual"]]
        bands = {}
        for band in ("predicted_late", "pred_safe_0_to_15m",
                     "pred_safe_15_to_30m", "pred_safe_30_to_60m",
                     "pred_safe_60m_plus"):
            subset = [r for r in tasks if slack_band(r["slack"]) == band]
            n_safe = sum(r["pred"] for r in subset)
            misses = sum(r["pred"] and not r["actual"] for r in subset)
            bands[band] = {
                "count": len(subset),
                "false_safe": misses,
                "false_safe_among_predicted_safe": misses/n_safe if n_safe else None,
            }
        by_route = {}
        for name, remote in (("local", False), ("remote", True)):
            subset = [r for r in tasks if r["remote"] == remote]
            n_pred = sum(r["pred"] for r in subset)
            misses = sum(r["pred"] and not r["actual"] for r in subset)
            by_route[name] = {
                "count": len(subset),
                "predicted_safe": n_pred,
                "false_safe": misses,
                "false_safe_among_predicted_safe": misses/n_pred if n_pred else None,
            }
        assert sum(v["count"] for v in bands.values()) == len(tasks)
        assert sum(v["count"] for v in by_route.values()) == len(tasks)
        report.append({
            "month": month, "day": day, "seed": seed, "policy": policy,
            "tasks": len(tasks),
            "predicted_safe": len(predicted_safe),
            "actually_missed": sum(not r["actual"] for r in tasks),
            "false_safe": len(false_safe),
            "false_safe_among_predicted_safe":
                len(false_safe)/len(predicted_safe) if predicted_safe else None,
            "positive_start_residual_count": sum(r["residual"] > 0 for r in tasks),
            "by_predicted_slack": bands,
            "by_route": by_route,
        })
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    with args.input.open(newline="",encoding="utf8") as f:
        report=scenario_risk_table(list(csv.DictReader(f)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report,indent=2))
    print("RETROSPECTIVE audit only; rows/tasks are not independent scenario replicates.")


if __name__=="__main__":
    main()
