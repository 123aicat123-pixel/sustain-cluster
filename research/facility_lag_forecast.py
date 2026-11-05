"""Frozen, leakage-checked one-step ahead facility energy/carbon study.

Pure NumPy; only the lagged row and known periodic step time can be used
to predict a target step. Simulator runs are separately partitioned by
calendar date. This is NOT an action-conditional carbon policy.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
import math
import numpy as np

LAG_FIELDS = (
    "energy_kwh", "it_power_kw", "hvac_power_kw",
    "dc_cpu_workload_fraction", "running_tasks", "pending_tasks",
    "ambient_temp_c", "effective_ci_g_per_kwh", "source_ci_g_per_kwh",
)
RIDGE_LAMBDA = 25.0


def _float(row, key):
    v = float(row[key])
    if not math.isfinite(v):
        raise ValueError(f"nonfinite {key}")
    return v


def lag_features(prior, target_step):
    """Known t index + t-1 metrics, no value read from current target."""
    # This function never accesses a target row.
    old = [_float(prior, field) for field in LAG_FIELDS]
    phase = 2 * math.pi * (int(target_step) % 96) / 96.0
    return old + [math.sin(phase), math.cos(phase)]


def make_pairs(rows, *, allowed_policy="queue_nsga2_with_transit"):
    """Return strictly adjacent lag/target pairs grouped by DC and run.

    Require unique steps and exactly 0..N-1 sequence in EACH run/DC.
    No feature may be constructed from another run, seed or DC.
    """
    grouped = defaultdict(dict)
    for r in rows:
        if str(r["policy"]) != allowed_policy:
            raise AssertionError("unexpected policy in lag forecasting cohort")
        key=(str(r["scenario_date"]),int(r["seed"]),str(r["dc_name"]))
        step=int(r["step_index"])
        if step in grouped[key] or step < 0:
            raise AssertionError("duplicate/negative simulator step")
        grouped[key][step]=r
    if not grouped:
        raise ValueError("empty training/evaluation records")
    pairs=[]
    for (day,seed,dc),steps in sorted(grouped.items()):
        sequence=sorted(steps)
        if sequence != list(range(len(sequence))) or len(sequence)<2:
            raise AssertionError("incomplete or noncontiguous DC telemetry")
        for target_step in sequence[1:]:
            target=steps[target_step]
            prior=steps[target_step-1]
            # No current-period information can enter lag_features.
            features=lag_features(prior,target_step)
            pairs.append({
                "scenario_date":day,"seed":seed,"dc_name":dc,
                "step_index":target_step,"x":features,
                "lag_energy":_float(prior,"energy_kwh"),
                "lag_carbon":_float(prior,"carbon_kg"),
                "lag_ci":_float(prior,"effective_ci_g_per_kwh"),
                "energy":_float(target,"energy_kwh"),
                "carbon":_float(target,"carbon_kg"),
            })
    return pairs


def fit_models(pairs, train_dates, *, lam=RIDGE_LAMBDA):
    """Regularized, training-only per-DC linear regression on energy."""
    if not math.isfinite(lam) or lam <= 0:
        raise ValueError("fixed positive ridge penalty required")
    training = [p for p in pairs if p["scenario_date"] in train_dates]
    if len(training) == 0 or set(train_dates)!={p["scenario_date"] for p in training}:
        raise AssertionError("some preregistered training dates are missing")
    models={}
    for dc in sorted({p["dc_name"] for p in pairs}):
        sample=[p for p in training if p["dc_name"]==dc]
        if len(sample)<12:
            raise AssertionError(f"too few training samples for {dc}")
        X=np.asarray([p["x"] for p in sample],dtype=float)
        y=np.asarray([p["energy"] for p in sample],dtype=float)
        mu=X.mean(axis=0)
        scale=X.std(axis=0)
        scale=np.where(scale<1e-10,1.0,scale)
        Z=(X-mu)/scale
        X1=np.column_stack([np.ones(len(Z)),Z])
        penalty=np.eye(X1.shape[1])*lam
        penalty[0,0]=0
        coeff=np.linalg.solve(X1.T@X1+penalty,X1.T@y)
        models[dc]={"mean":mu.tolist(),"scale":scale.tolist(),
                    "coef":coeff.tolist(),
                    "mean_energy":float(y.mean()),
                    "mean_carbon":float(np.mean([p["carbon"] for p in sample])),
                    "training_pairs":len(sample)}
    expected=set(p["dc_name"] for p in pairs)
    if set(models)!=expected:
        raise AssertionError("some DCs have no fitted training model")
    return models


def predict(models,pair):
    model=models[pair["dc_name"]]
    X=np.asarray(pair["x"],dtype=float)
    z=(X-np.asarray(model["mean"]))/np.asarray(model["scale"])
    pred_energy=max(0.0,float(np.dot(np.r_[1,z],model["coef"])))
    return {
        "ridge_energy":pred_energy,
        "ridge_carbon":pred_energy*pair["lag_ci"]/1000,
        "persist_energy":pair["lag_energy"],
        "persist_carbon":pair["lag_carbon"],
        "site_mean_energy":model["mean_energy"],
        "site_mean_carbon":model["mean_carbon"],
    }


def _metrics(values):
    err=np.asarray(values,dtype=float)
    return {"n":len(err),"mae":float(np.mean(abs(err))),
            "bias":float(np.mean(err)),
            "rmse":float(np.sqrt(np.mean(err**2)))}


def evaluate(pairs,models,*,dates):
    results=[]
    for day in dates:
        for dc in sorted(models):
            for seed in sorted({p["seed"] for p in pairs}):
                sample=[p for p in pairs if p["scenario_date"]==day
                        and p["dc_name"]==dc and p["seed"]==seed]
                if not sample:
                    raise AssertionError(f"missing evaluation cohort {day}/{dc}/{seed}")
                preds=[predict(models,p) for p in sample]
                record={"date":day,"seed":seed,"datacenter":dc,"n":len(sample)}
                for target in ("energy","carbon"):
                    for method in ("ridge","persist","site_mean"):
                        residuals=[x[f"{method}_{target}"]-p[target]
                                   for p,x in zip(sample,preds)]
                        record[f"{method}_{target}"]=_metrics(residuals)
                results.append(record)
    return results


def split_digest(pairs,dates):
    manifest=sorted((p["scenario_date"],p["seed"],p["dc_name"],
                    p["step_index"]) for p in pairs
                    if p["scenario_date"] in dates)
    return hashlib.sha256(json.dumps(manifest,separators=(",",":")).encode()).hexdigest()
