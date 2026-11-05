"""Audit frozen one-step forecast MAE separately for admission and drain.

Read-only on an existing fitted-model report. This script never refits,
selects hyperparameters or updates the online routing policy.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from research.facility_lag_benchmark import DATE_FILE, TRAIN, DEV, TEST
from research.facility_lag_forecast import make_pairs, predict, _metrics


def phase_audit(pairs, original, admission_steps=16):
    """Assert unchanged all-step metrics before reporting phase breakdown."""
    if admission_steps <= 1:
        raise ValueError("need admission first-step lag")
    models=original["models"]
    recorded=(original["train_metrics"]+original["dev_metrics"]
              +original["test_metrics"])
    indexed={(r["date"],int(r["seed"]),r["datacenter"]):r for r in recorded}
    groups={}
    for p in pairs:
        key=(p["scenario_date"],int(p["seed"]),p["dc_name"])
        groups.setdefault(key,[]).append(p)
    if set(indexed)!=set(groups):
        raise AssertionError("original forecast and telemetry cohorts disagree")

    result=[]
    for key, full in sorted(groups.items()):
        reference=indexed[key]
        if len(full)!=reference["n"]:
            raise AssertionError("full-horizon pair count mismatch")
        full.sort(key=lambda p:p["step_index"])
        predicted=[predict(models,p) for p in full]
        for target in ("energy","carbon"):
            for method in ("ridge","persist","site_mean"):
                residuals=[x[f"{method}_{target}"]-p[target]
                           for p,x in zip(full,predicted)]
                metrics=_metrics(residuals)
                ref=reference[f"{method}_{target}"]
                for field in ("n","mae","bias","rmse"):
                    if not math.isclose(metrics[field],ref[field],
                                        rel_tol=1e-9,abs_tol=1e-9):
                        raise AssertionError(
                            f"frozen full-period prediction changed {key} {method} {target} {field}")
        for phase in ("admission","drain"):
            picks=[(p,out) for p,out in zip(full,predicted)
                   if (1 <= p["step_index"] < admission_steps)
                   == (phase=="admission")]
            if not picks:
                raise AssertionError(f"empty forecast phase {key} {phase}")
            record={"date":key[0],"seed":key[1],"datacenter":key[2],
                    "phase":phase,"n":len(picks)}
            for target in ("energy","carbon"):
                for method in ("ridge","persist","site_mean"):
                    diffs=[out[f"{method}_{target}"]-p[target] for p,out in picks]
                    scores=_metrics(diffs)
                    scores["p95_abs"]=sorted(abs(v) for v in diffs)[
                        max(0, math.ceil(0.95*len(diffs))-1)]
                    record[f"{method}_{target}"]=scores
            result.append(record)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--directory",required=True,type=Path)
    parser.add_argument("--forecast",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    original=json.loads(args.forecast.read_text(encoding="utf8"))
    data=[]
    manifest={}
    for date,stem in DATE_FILE.items():
        path=args.directory/(stem+"_facility_cells.csv")
        raw=path.read_bytes()
        manifest[date]=hashlib.sha256(raw).hexdigest()
        rows=list(csv.DictReader(raw.decode("utf8").splitlines()))
        for row in rows:
            row["scenario_date"]=date
        data.extend(rows)
    pairs=make_pairs(data)
    breakdown=phase_audit(pairs,original)
    result={"status":"frozen model, diagnostic phase breakdown, no retuning",
            "train_dates":list(TRAIN),"dev_dates":list(DEV),
            "test_dates":list(TEST),"facility_csv_sha256":manifest,
            "phase_metrics":breakdown}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf8")
    for day in list(DEV)+list(TEST):
        for phase in ("admission","drain"):
            selection=[r for r in breakdown if r["date"]==day and r["phase"]==phase]
            if not selection:
                raise AssertionError("missing evaluation date/phase")
            for target in ("energy","carbon"):
                n=sum(r["n"] for r in selection)
                mae={m:sum(r["n"]*r[f"{m}_{target}"]["mae"] for r in selection)/n
                     for m in ("ridge","persist","site_mean")}
                print("PHASE",day,phase,target,"cell-weighted MAE",mae,flush=True)
    print("Reconciled every original per-center/seed full-period forecast metric",flush=True)


if __name__=="__main__":
    main()
