"""Post-hoc physical-carbon attribution. Never used by online schedulers."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from research.facility_power_carbon_attribution import decompose_power_carbon
from research.facility_telemetry import (
    verify_facility_telemetry, paired_carbon_attribution
)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--prefix",required=True,type=Path)
    parser.add_argument("--reference",default="queue_nsga2_with_transit")
    parser.add_argument("--candidate",default="queue_nsga2_front_carbon_taskwise")
    args=parser.parse_args()
    stem=str(args.prefix)
    runs=json.loads(Path(stem+".json").read_text(encoding="utf8"))
    with Path(stem+"_facility_cells.csv").open(newline="",encoding="utf8") as f:
        rows=list(csv.DictReader(f))
    audit=verify_facility_telemetry(rows,runs)
    pairs=paired_carbon_attribution(rows,reference=args.reference,
                                    candidate=args.candidate)
    power_parts=decompose_power_carbon(
        rows,reference=args.reference,candidate=args.candidate)
    power_by_seed={r["seed"]:r for r in power_parts}
    for pair in pairs:
        seed=pair["seed"]
        b=next(r for r in runs if r["seed"]==seed and r["policy"]==args.reference)
        c=next(r for r in runs if r["seed"]==seed and r["policy"]==args.candidate)
        t=pair["total"]
        power=power_by_seed[seed]["total"]
        if abs(power["delta_carbon_kg"]-t["carbon_delta_kg"])>1e-7:
            raise AssertionError("power/CI attribution does not reconcile")
        print("power split",seed,
              "IT",power["it_carbon_kg"],"HVAC",power["hvac_carbon_kg"],
              "grid adjustment",power["grid_adjustment_carbon_kg"],
              "effective CI",power["effective_ci_carbon_kg"])
        measured=c["facility_carbon_kg"]-b["facility_carbon_kg"]
        if abs(t["carbon_delta_kg"]-measured)>1e-5:
            raise AssertionError(f"facility difference does not reconcile seed {seed}")
        print("seed",seed,"facility-carbon-delta-kg",t["carbon_delta_kg"],
              "energy-effect-kg",t["energy_effect_carbon_kg"],
              "effective-CI-effect-kg",t["effective_ci_effect_carbon_kg"],
              "actual-SLA",b["sla_violated"],c["sla_violated"],
              "transmission-carbon-delta-kg",
              c["transmission_carbon_kg"]-b["transmission_carbon_kg"])
    result={"reference":args.reference,"candidate":args.candidate,
            "reconciliation":audit,"facility_carbon_attribution":pairs,
            "power_carbon_attribution":power_parts}
    Path(stem+"_carbon_attribution.json").write_text(
        json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf8")


if __name__=="__main__":
    main()
