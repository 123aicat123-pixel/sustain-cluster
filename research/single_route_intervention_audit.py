"""Paired full-simulator audit of a *single* changed dispatch choice.

Reports the total downstream simulated consequences of one routing action.
This is exploratory and explicitly NOT a causal per-task power coefficient,
an estimator fitted on future outcomes, or a deployment carbon guarantee.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from research.paired_task_analysis import compare_task_rows
from research.facility_power_carbon_attribution import decompose_power_carbon


CONTROL = "probe_control"
ARMS = ("probe_low_ci", "probe_high_ci")


def _close(actual, expected, name):
    if not math.isclose(float(actual), float(expected), abs_tol=1e-6,
                        rel_tol=1e-8):
        raise AssertionError(f"{name} not reconciled: {actual} != {expected}")


def audit_route_probe(runs, tasks, cells):
    """Require exact matched arrivals and EXACTLY ONE altered destination.

    Task-level differences in start/finish/SLA of *other* jobs are expected:
    they are downstream effects of the one initial route intervention.
    """
    if len(runs) == 0:
        raise AssertionError("missing simulator runs")
    if len({(int(r["seed"]), str(r["policy"])) for r in runs}) != len(runs):
        raise AssertionError("duplicated seed-policy summary")
    result = []
    paired = compare_task_rows(tasks, reference=CONTROL)
    pair_index = {(int(x["seed"]), x["policy"]): x for x in paired}
    by_runs = {(int(r["seed"]), r["policy"]): r for r in runs}
    for seed in sorted({int(r["seed"]) for r in runs}):
        expected = {(seed, name) for name in (CONTROL,) + ARMS}
        if not expected.issubset(by_runs):
            raise AssertionError(f"missing intervention arm for seed {seed}")
        base = by_runs[(seed, CONTROL)]
        base_probe = base.get("probe_intervention")
        if not base_probe or base_probe.get("arm") != "control":
            raise AssertionError("missing pre-registered control probe")
        if int(base_probe["control_dc_id"]) != int(base_probe["selected_dc_id"]):
            raise AssertionError("control secretly changed its action")
        if not base["fully_drained"] or base["fallback_assignments"]:
            raise AssertionError("control failed to complete its original cohort")
        for arm in ARMS:
            candidate = by_runs[(seed, arm)]
            probe = candidate.get("probe_intervention")
            if not probe or probe.get("arm") != arm.removeprefix("probe_"):
                raise AssertionError("missing exact candidate intervention metadata")
            if (probe["task_name"] != base_probe["task_name"]
                    or int(probe["task_index"]) != int(base_probe["task_index"])
                    or int(probe["control_dc_id"]) != int(base_probe["control_dc_id"])):
                raise AssertionError("different original action or sampled task")
            if int(probe["chosen_action"]) == int(probe["original_action"]):
                raise AssertionError("candidate route not actually perturbed")
            if (not candidate["fully_drained"] or candidate["fallback_assignments"]
                    or candidate["tasks_dispatched"] != base["tasks_dispatched"]
                    or candidate["tasks_finished"] != base["tasks_finished"]):
                raise AssertionError("simulator lifecycle/paired cohort mismatch")

            pair = pair_index[(seed, arm)]
            if pair["destination_changes"] != 1:
                raise AssertionError(
                    f"expected exactly ONE different route, not {pair['destination_changes']}, seed {seed}"
                )
            all_rows = [row for row in tasks if int(row["seed"]) == seed]
            control_rows = {(r["arrival_utc"],r["job_name"]):r
                            for r in all_rows if r["policy"] == CONTROL}
            candidate_rows = {(r["arrival_utc"],r["job_name"]):r
                              for r in all_rows if r["policy"] == arm}
            route_keys = [k for k in control_rows if
                          control_rows[k]["dest_dc_id"] != candidate_rows[k]["dest_dc_id"]]
            if len(route_keys) != 1 or route_keys[0][1] != probe["task_name"]:
                raise AssertionError("changed route is not the controlled target")
            task_key = route_keys[0]
            if (int(control_rows[task_key]["dest_dc_id"]) != int(probe["control_dc_id"])
                    or int(candidate_rows[task_key]["dest_dc_id"]) != int(probe["selected_dc_id"])):
                raise AssertionError("actual task destination contradicts probe metadata")
            # SOURCE grid CI is current-time manager signal, NOT the
            # battery-adjusted effective intensity of finished facility energy.
            source_base = float(base_probe["observed_selected_ci"])
            source_new = float(probe["observed_selected_ci"])
            proxy_kwh = (float(probe["original_cpu_cores"])
                         * float(probe["duration_minutes"]) / 60 * 0.006)
            fixed_proxy_delta = proxy_kwh * (source_new-source_base)/1000

            # Complete day/seed DC-cell aligned physics audit.
            case_cells = [r for r in cells if int(r["seed"]) == seed
                          and r["policy"] in (CONTROL, arm)]
            parts = decompose_power_carbon(
                case_cells, reference=CONTROL,candidate=arm)
            if len(parts) != 1:
                raise AssertionError("facility decomposition not unique")
            physical = parts[0]["total"]
            facility_delta = (float(candidate["facility_carbon_kg"])
                              -float(base["facility_carbon_kg"]))
            transfer_delta = (float(candidate["transmission_carbon_kg"])
                              -float(base["transmission_carbon_kg"]))
            total_delta = (float(candidate["reported_total_carbon_kg"])
                           -float(base["reported_total_carbon_kg"]))
            _close(physical["delta_carbon_kg"], facility_delta, "facility carbon")
            _close(facility_delta+transfer_delta, total_delta, "total carbon")
            result.append({
                "seed":seed,"arm":arm,"job_name":probe["task_name"],
                "arrival_utc":task_key[0],
                "original_dc_id":int(probe["control_dc_id"]),
                "new_dc_id":int(probe["selected_dc_id"]),
                "control_source_ci_g_per_kwh":source_base,
                "new_source_ci_g_per_kwh":source_new,
                "fixed_6w_core_carbon_proxy_delta_kg":fixed_proxy_delta,
                "measured_facility_carbon_delta_kg":facility_delta,
                "measured_transfer_carbon_delta_kg":transfer_delta,
                "measured_total_carbon_delta_kg":total_delta,
                "facility_it_effect_kg":physical["it_carbon_kg"],
                "facility_hvac_effect_kg":physical["hvac_carbon_kg"],
                "facility_grid_adjustment_effect_kg":physical["grid_adjustment_carbon_kg"],
                "facility_effective_ci_effect_kg":physical["effective_ci_carbon_kg"],
                "measured_total_cost_delta_usd":float(
                    candidate["reported_total_cost_usd"])-float(
                    base["reported_total_cost_usd"]),
                "sla_baseline_misses":int(base["sla_violated"]),
                "sla_candidate_misses":int(candidate["sla_violated"]),
                "sla_harmed":pair["sla_harmed"],
                "sla_rescued":pair["sla_rescued"],
                "changed_task_routes":pair["destination_changes"],
                "other_task_start_changes":pair["start_time_changes"],
                "other_task_finish_changes":pair["finish_time_changes"],
            })
    if len(result) != len({int(r["seed"]) for r in runs})*2:
        raise AssertionError("unexpected number of matched comparisons")
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prefix",type=Path,required=True)
    args=p.parse_args()
    stem=str(args.prefix)
    runs=json.loads(Path(stem+".json").read_text(encoding="utf8"))
    with Path(stem+"_completed_tasks.csv").open(newline="",encoding="utf8") as f:
        tasks=list(csv.DictReader(f))
    with Path(stem+"_facility_cells.csv").open(newline="",encoding="utf8") as f:
        cells=list(csv.DictReader(f))
    report=audit_route_probe(runs,tasks,cells)
    path=Path(stem+"_single_route_audit.json")
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf8")
    for r in report:
        print("INTERVENTION",r["seed"],r["arm"],
              "changed_routes",r["changed_task_routes"],
              "source-CI-6W-proxy-kg",r["fixed_6w_core_carbon_proxy_delta_kg"],
              "facility-kg",r["measured_facility_carbon_delta_kg"],
              "transfer-kg",r["measured_transfer_carbon_delta_kg"],
              "SLA",r["sla_baseline_misses"],"->",r["sla_candidate_misses"],
              "IT-kg",r["facility_it_effect_kg"],
              "HVAC-kg",r["facility_hvac_effect_kg"],flush=True)
    print("Wrote",path,flush=True)


if __name__=="__main__":
    main()
