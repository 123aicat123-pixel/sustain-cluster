"""Independent post-simulation, time/DC-matched power-to-carbon accounting.

The IT/HVAC/battery-grid/effective-CI effects sum EXACTLY to a carbon delta,
with a fixed reference-CI decomposition order. Attribution is mathematical,
not causal; never feed these realized values into an online decision policy.
"""
from __future__ import annotations

from collections import defaultdict
import math


def decompose_power_carbon(rows, *, reference="queue_nsga2_with_transit",
                           candidate="queue_nsga2_front_carbon_taskwise",
                           step_hours=0.25):
    if not math.isfinite(step_hours) or step_hours <= 0:
        raise ValueError("invalid simulator step length")
    by_key = {}
    for row in rows:
        key = (int(row["seed"]), str(row["policy"]),
               int(row["step_index"]), str(row["dc_name"]))
        if key in by_key:
            raise AssertionError(f"duplicate power cell {key}")
        by_key[key] = row
    seeds = sorted({k[0] for k in by_key})
    if not seeds:
        raise ValueError("no facility telemetry rows")

    def cell_numeric(cell, name):
        v = cell.get(name)
        if v in (None, ""):
            raise ValueError(f"missing {name} in a required facility cell")
        out = float(v)
        if not math.isfinite(out):
            raise ValueError(f"nonfinite {name}")
        return out

    output = []
    for seed in seeds:
        before = {(k[2], k[3]): v for k, v in by_key.items()
                  if k[0] == seed and k[1] == reference}
        after = {(k[2], k[3]): v for k, v in by_key.items()
                 if k[0] == seed and k[1] == candidate}
        if not before or set(before) != set(after):
            raise AssertionError(f"unequal DC/time cells for seed={seed}")
        parts = defaultdict(lambda: {
            "cells": 0, "delta_energy_kwh": 0.0,
            "delta_carbon_kg": 0.0, "it_carbon_kg": 0.0,
            "hvac_carbon_kg": 0.0,
            "grid_adjustment_carbon_kg": 0.0,
            "effective_ci_carbon_kg": 0.0,
            "changed_ci_cells": 0,
        })
        for key in sorted(before):
            b, t = before[key], after[key]
            E0, E1 = (cell_numeric(x, "energy_kwh") for x in (b, t))
            I0, I1 = (cell_numeric(x, "effective_ci_g_per_kwh") for x in (b, t))
            C0, C1 = (cell_numeric(x, "carbon_kg") for x in (b, t))
            P0_it, P1_it = (cell_numeric(x, "it_power_kw") for x in (b, t))
            P0_h, P1_h = (cell_numeric(x, "hvac_power_kw") for x in (b, t))
            P0, P1 = (cell_numeric(x, "total_dc_power_kw") for x in (b, t))
            if any(x < -1e-9 for x in (E0, E1, I0, I1, C0, C1)):
                raise ValueError("negative physical energy/CI/carbon input")
            for a, p, name in ((P0,P0_it+P0_h,"reference"),
                               (P1,P1_it+P1_h,"candidate")):
                if not math.isclose(a,p,rel_tol=1e-8,abs_tol=1e-7):
                    raise AssertionError(f"IT + HVAC != total power: {name} {key}")
            delta_energy = E1-E0
            it = (P1_it-P0_it)*step_hours*I0/1000
            hvac = (P1_h-P0_h)*step_hours*I0/1000
            grid_adjust = (delta_energy - (P1-P0)*step_hours)*I0/1000
            effective_ci = E1*(I1-I0)/1000
            delta_carbon = C1-C0
            if not math.isclose(delta_carbon, it+hvac+grid_adjust+effective_ci,
                                rel_tol=1e-8,abs_tol=1e-7):
                raise AssertionError(f"power-carbon split does not reconcile {key}")
            for group in (parts["__all__"],parts[key[1]]):
                group["cells"] += 1
                group["delta_energy_kwh"] += delta_energy
                group["delta_carbon_kg"] += delta_carbon
                group["it_carbon_kg"] += it
                group["hvac_carbon_kg"] += hvac
                group["grid_adjustment_carbon_kg"] += grid_adjust
                group["effective_ci_carbon_kg"] += effective_ci
                group["changed_ci_cells"] += int(abs(I1-I0)>1e-8)
        total = parts.pop("__all__")
        output.append({"seed": seed, "reference": reference,
                       "candidate": candidate, "step_hours": step_hours,
                       "total": dict(total),
                       "by_datacenter": dict(sorted(parts.items()))})
    return output
