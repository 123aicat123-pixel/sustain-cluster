"""Run frozen facility-lag forecasting over date-separated telemetry CSVs."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

from research.facility_lag_forecast import (
    RIDGE_LAMBDA, make_pairs, fit_models, evaluate, split_digest
)

TRAIN=("06-15","11-12")
DEV=("05-19",)
TEST=("03-09","09-21")
DATE_FILE={
    "06-15":"train_june15",
    "11-12":"train_nov12",
    "05-19":"dev_may19",
    "03-09":"test_mar09",
    "09-21":"test_sep21",
}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--directory",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    rows=[]
    for date,stub in DATE_FILE.items():
        p=args.directory/(stub+"_facility_cells.csv")
        if not p.is_file():
            raise FileNotFoundError(f"required split {date}: {p}")
        with p.open(newline="",encoding="utf8") as f:
            data=list(csv.DictReader(f))
        if not data:
            raise AssertionError(f"empty facility telemetry for {date}")
        for r in data:
            r["scenario_date"]=date
        rows.extend(data)
    pairs=make_pairs(rows)
    dates={p["scenario_date"] for p in pairs}
    if dates != set(TRAIN+DEV+TEST):
        raise AssertionError("missing or unexpected calendar split")
    seeds=sorted({p["seed"] for p in pairs})
    if seeds!=[901,1701]:
        raise AssertionError(f"unexpected validation seeds {seeds}")
    models=fit_models(pairs,TRAIN)
    report={
        "status":"offline diagnostic, not action-conditioned marginal carbon",
        "lambda":RIDGE_LAMBDA,
        "train_dates":list(TRAIN),"dev_dates":list(DEV),"test_dates":list(TEST),
        "training_manifest_sha256":split_digest(pairs,TRAIN),
        "dev_manifest_sha256":split_digest(pairs,DEV),
        "test_manifest_sha256":split_digest(pairs,TEST),
        "models":models,
        "train_metrics":evaluate(pairs,models,dates=TRAIN),
        "dev_metrics":evaluate(pairs,models,dates=DEV),
        "test_metrics":evaluate(pairs,models,dates=TEST),
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf8")
    for part in ("dev_metrics","test_metrics"):
        for day in sorted({r["date"] for r in report[part]}):
            for target in ("energy","carbon"):
                cells=[r for r in report[part] if r["date"]==day]
                count=sum(c["n"] for c in cells)
                vals={}
                for method in ("ridge","persist","site_mean"):
                    vals[method]=sum(c["n"]*c[f"{method}_{target}"]["mae"]
                                     for c in cells)/count
                print("FROZEN",part,day,target,"weighted_cell_mae",vals,flush=True)
    print("Wrote",args.output,flush=True)


if __name__=="__main__":
    main()
