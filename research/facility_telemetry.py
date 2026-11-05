"""Read-only facility telemetry and exact matched-cell carbon attribution.

Everything is collected AFTER the simulator step. Never expose reported
facility energy, battery outcomes, or realized carbon to an online scheduler.
The decomposition is an accounting identity, not a causal energy model.
"""
from __future__ import annotations

from collections import defaultdict
import math

from research.physical_accounting import validate_datacenter_step


OPTIONAL_DC_METRICS = {
    "it_power_kw": "dc_ITE_total_power_kW",
    "hvac_power_kw": "dc_HVAC_total_power_kW",
    "total_dc_power_kw": "dc_total_power_kW",
    "ambient_temp_c": "dc_exterior_ambient_temp",
    "dc_cpu_workload_fraction": "dc_cpu_workload_fraction",
}


def facility_cell(*, seed, policy, step_index, dc_name, dc_info):
    """Extract only numeric step results; no objects or future state."""
    validate_datacenter_step(dc_info)
    common = dc_info["__common__"]
    battery = dc_info["agent_bat"]
    dc = dc_info["agent_dc"]
    result = {
        "seed": int(seed),
        "policy": str(policy),
        "step_index": int(step_index),
        "dc_name": str(dc_name),
        "energy_kwh": float(common["energy_consumption_kwh"]),
        "carbon_kg": float(common["carbon_emissions_kg"]),
        "cost_usd": float(common["energy_cost_USD"]),
        "effective_ci_g_per_kwh": float(battery["bat_avg_CI"]),
        "source_ci_g_per_kwh": float(common["ci"]),
        "price_usd_per_mwh": float(common["price_USD_kwh"]),
        "running_tasks": int(common["running_tasks"]),
        "pending_tasks": int(common["pending_tasks"]),
    }
    for name, key in OPTIONAL_DC_METRICS.items():
        raw = dc.get(key)
        result[name] = None if raw is None else float(raw)
    for name, value in result.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise AssertionError(f"nonfinite {name} at step {step_index}")
    if result["step_index"] < 0:
        raise AssertionError("negative simulator step")
    return result


def paired_carbon_attribution(rows, *, reference="queue_nsga2_with_transit",
                              candidate="queue_nsga2_front_carbon_taskwise"):
    """Decompose actual per-cell emissions difference without aggregating CI.

    ΔCO2 = (E_candidate - E_reference)*CI_reference/1000
         + E_candidate*(CI_candidate - CI_reference)/1000.

    This asymmetric exact decomposition assigns the interaction to the
    effective-CI term. It is NOT a causal decomposition into battery vs load.
    """
    by_key = {}
    for row in rows:
        key = (int(row["seed"]), str(row["policy"]),
               int(row["step_index"]), str(row["dc_name"]))
        if key in by_key:
            raise AssertionError(f"duplicate facility telemetry key {key}")
        by_key[key] = row
    seed_policies = {(key[0], key[1]) for key in by_key}
    seeds = sorted({x[0] for x in seed_policies})
    out = []
    for seed in seeds:
        b = {(k[2], k[3]): v for k,v in by_key.items()
             if k[0] == seed and k[1] == reference}
        c = {(k[2], k[3]): v for k,v in by_key.items()
             if k[0] == seed and k[1] == candidate}
        if not b or not c or b.keys() != c.keys():
            raise AssertionError(f"missing or mismatched facility/time cells, seed {seed}")
        parts = defaultdict(lambda: {"cells":0,"energy_delta_kwh":0.0,
            "carbon_delta_kg":0.0,"cost_delta_usd":0.0,
            "energy_effect_carbon_kg":0.0,"effective_ci_effect_carbon_kg":0.0,
            "effective_ci_changed_cells":0,"source_ci_changed_cells":0})
        for key in sorted(b):
            base, trial = b[key], c[key]
            E0, E1 = float(base["energy_kwh"]),float(trial["energy_kwh"])
            I0, I1 = float(base["effective_ci_g_per_kwh"]),float(trial["effective_ci_g_per_kwh"])
            delta = float(trial["carbon_kg"])-float(base["carbon_kg"])
            energy_effect=(E1-E0)*I0/1000
            ci_effect=E1*(I1-I0)/1000
            if not math.isclose(delta,energy_effect+ci_effect,rel_tol=1e-9,abs_tol=1e-8):
                raise AssertionError(f"carbon decomposition mismatch: {key}")
            for group in (parts["__all__"],parts[key[1]]):
                group["cells"]+=1
                group["energy_delta_kwh"]+=E1-E0
                group["carbon_delta_kg"]+=delta
                group["cost_delta_usd"]+=float(trial["cost_usd"])-float(base["cost_usd"])
                group["energy_effect_carbon_kg"]+=energy_effect
                group["effective_ci_effect_carbon_kg"]+=ci_effect
                group["effective_ci_changed_cells"]+=int(abs(I1-I0)>1e-8)
                group["source_ci_changed_cells"]+=int(
                    abs(float(trial["source_ci_g_per_kwh"])
                       -float(base["source_ci_g_per_kwh"]))>1e-8
                )
        total=parts.pop("__all__")
        out.append({"seed":seed,"reference":reference,"candidate":candidate,
                    "total":dict(total),"by_datacenter":dict(sorted(parts.items()))})
    return out


def verify_facility_telemetry(rows, aggregate_runs):
    """Reconcile every post-step DC cell with simulator run totals.

    Requiring complete rectangular (step, DC) matrices catches missing cells,
    duplicated steps, and accidental policy/seed mixing.
    """
    by_run = defaultdict(list)
    keys = set()
    for cell in rows:
        k = (int(cell["seed"]), str(cell["policy"]),
             int(cell["step_index"]), str(cell["dc_name"]))
        if k in keys:
            raise AssertionError(f"duplicate telemetry cell {k}")
        keys.add(k)
        energy = float(cell["energy_kwh"])
        carbon = float(cell["carbon_kg"])
        cost = float(cell["cost_usd"])
        ci = float(cell["effective_ci_g_per_kwh"])
        price = float(cell["price_usd_per_mwh"])
        if any(not math.isfinite(x) for x in (energy, carbon, cost, ci, price)):
            raise AssertionError(f"invalid facility telemetry cell {k}")
        if not math.isclose(carbon, energy * ci / 1000,
                            rel_tol=1e-8, abs_tol=1e-7):
            raise AssertionError(f"facility cell carbon identity failed {k}")
        if not math.isclose(cost, energy * price / 1000,
                            rel_tol=1e-8, abs_tol=1e-7):
            raise AssertionError(f"facility cell cost identity failed {k}")
        by_run[k[:2]].append(cell)
    expected = {(int(r["seed"]), str(r["policy"])) for r in aggregate_runs}
    if len(expected) != len(aggregate_runs) or set(by_run) != expected:
        raise AssertionError("facility telemetry run keys do not match summary")
    out = []
    for run in aggregate_runs:
        key = (int(run["seed"]), str(run["policy"]))
        cells = by_run[key]
        time_steps = int(run["steps_completed"])
        dc_names = {str(c["dc_name"]) for c in cells}
        expected_cells = {(step, dc) for step in range(time_steps)
                          for dc in dc_names}
        actual_cells = {(int(c["step_index"]),str(c["dc_name"])) for c in cells}
        if expected_cells != actual_cells or not dc_names:
            raise AssertionError(f"missing DC/step cell(s) for {key}")
        for col, total in (
            ("energy_kwh","facility_energy_kwh"),
            ("carbon_kg","facility_carbon_kg"),
            ("cost_usd","facility_cost_usd"),
        ):
            value = math.fsum(float(c[col]) for c in cells)
            if not math.isclose(value,float(run[total]),
                                rel_tol=1e-9, abs_tol=1e-6):
                raise AssertionError(f"facility sum mismatch {key}: {col}")
        out.append({"seed":key[0],"policy":key[1],
                    "datacenters":len(dc_names),"steps":time_steps,
                    "cells":len(cells),"reconciled":True})
    return out
