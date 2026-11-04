"""Matched-action SustainCluster baseline pilot (NOT publication-grade results).

All policies select a data-center action per task and run through the SAME
TaskSchedulingEnv.step manual_rl routing path. This avoids the upstream
native-rule-vs-RL transmission-path asymmetry. No policy defers tasks in this
pilot; future temporal policies require a separate action-matched experiment.

Usage:
python -m research_sci.run_pilot --steps 8 --drain-steps 24 --seeds 42
"""
import argparse
import copy
import csv
import json
import math
import random
import statistics
import tempfile
from pathlib import Path

import numpy as np
import yaml

from research_sci.policies import SpatialPolicy
from train_SAC_agent import make_env


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/env/sim_config.yaml"
DC_CONFIG = ROOT / "configs/env/datacenters.yaml"
REWARD_CONFIG = ROOT / "configs/env/reward_config.yaml"


def run_once(name, seed, steps, drain_steps):
    if steps < 1 or drain_steps < 1:
        raise ValueError("Both admission and drain steps must be positive")

    random.seed(seed)
    np.random.seed(seed)
    config = copy.deepcopy(yaml.safe_load(CONFIG.read_text(encoding="utf-8")))
    settings = config["simulation"]
    settings.update({
        "strategy": "manual_rl",
        "single_action_mode": False,
        "disable_defer_action": False,
        "shuffle_datacenters": False,
        "use_tensorboard": False,
        "duration_days": max(2, math.ceil((steps + drain_steps + 1) / 96)),
    })
    with tempfile.TemporaryDirectory(prefix="sci_pilot_") as tmp:
        cfg = Path(tmp) / "simulation.yaml"
        cfg.write_text(yaml.safe_dump(config), encoding="utf-8")
        env = make_env(str(cfg), str(DC_CONFIG), str(REWARD_CONFIG),
                       writer=None, logger=None)
        try:
            if env.single_action_mode or env.disable_defer_action:
                raise AssertionError("Pilot requires per-task actions and common defer-capable action indexing")

            env.reset(seed=seed)
            # Stop admitting NEW tasks after 'steps' decisions, but allow a
            # fixed additional drain horizon for tasks already dispatched.
            cutoff = env.start_time + steps * env.time_step
            original_loader = env.cluster_manager.get_tasks_for_timestep

            def fixed_admission(time):
                return [] if time >= cutoff else original_loader(time)

            env.cluster_manager.get_tasks_for_timestep = fixed_admission
            policy = SpatialPolicy(name)
            id_to_action = {
                dc.dc_id: index + 1
                for index, dc in enumerate(env.cluster_manager.datacenters.values())
            }
            if len(id_to_action) != len(env.cluster_manager.datacenters):
                raise AssertionError("Duplicate data center IDs")

            result = {
                "policy": name, "seed": seed, "admission_steps": steps,
                "drain_steps": drain_steps,
                "tasks_dispatched": 0, "tasks_finished": 0,
                "sla_met": 0, "sla_violated": 0,
                "fallback_to_origin": 0,
                "facility_carbon_kg": 0.0, "network_carbon_kg": 0.0,
                "facility_cost_usd": 0.0, "network_cost_usd": 0.0,
                "facility_energy_kwh": 0.0, "network_energy_kwh": 0.0,
                "pending_last": 0, "running_last": 0, "in_transit_last": 0,
            }
            dispatched = set()
            finished = set()

            for _ in range(steps + drain_steps):
                tasks = list(env.current_tasks)
                actions = []
                for task in tasks:
                    dc_id, fallback = policy.choose(
                        task, env.cluster_manager.datacenters,
                        env.current_time, env.cluster_manager,
                        step_seconds=int(env.time_step.total_seconds()),
                    )
                    if dc_id not in id_to_action:
                        raise AssertionError("Policy returned an unknown data center")
                    actions.append(id_to_action[dc_id])
                    result["fallback_to_origin"] += int(fallback)
                    dispatched.add(task)

                _, _, terminated, truncated, info = env.step(actions)

                for dc_info in info["datacenter_infos"].values():
                    common = dc_info["__common__"]
                    result["facility_energy_kwh"] += float(common["energy_consumption_kwh"])
                    result["facility_cost_usd"] += float(common["energy_cost_USD"])
                    result["facility_carbon_kg"] += float(common["carbon_emissions_kg"])
                    result["sla_met"] += int(common["__sla__"]["met"])
                    result["sla_violated"] += int(common["__sla__"]["violated"])
                    result["tasks_finished"] += int(common["finished_tasks_count"])
                    completed_here = common["tasks_finished_this_step_objects"]
                    if len(completed_here) != len(set(completed_here)):
                        raise AssertionError("Repeated task in a completion batch")
                    if finished.intersection(completed_here):
                        raise AssertionError("Task completed more than once")
                    finished.update(completed_here)

                # Upstream info fields 'total_*' are TRANSMISSION ONLY.
                result["network_carbon_kg"] += float(info["total_emissions_kg"])
                result["network_energy_kwh"] += float(info["total_energy_kwh"])
                result["network_cost_usd"] += float(info["transmission_cost_total_usd"])
                if terminated or truncated:
                    # The environment must cover all requested pilot steps.
                    if env.current_time < cutoff + drain_steps * env.time_step:
                        raise AssertionError("Simulation ended early")

            pending = [task for dc in env.cluster_manager.datacenters.values()
                       for task in dc.pending_tasks]
            running = [task for dc in env.cluster_manager.datacenters.values()
                       for task in dc.running_tasks]
            in_transit = [task for _, task, _ in env.in_transit_tasks]
            waiting = list(env.current_tasks)
            all_states = list(finished) + pending + running + in_transit + waiting
            if len(all_states) != len(set(all_states)):
                raise AssertionError("Task appears in multiple lifecycle states")
            if set(all_states) != dispatched:
                raise AssertionError("Dispatched tasks not conserved")
            if result["tasks_finished"] != len(finished):
                raise AssertionError("Completion counts inconsistent")
            if result["sla_met"] + result["sla_violated"] != len(finished):
                raise AssertionError("SLA completion counts inconsistent")

            result["tasks_dispatched"] = len(dispatched)
            result["pending_last"] = len(pending)
            result["running_last"] = len(running)
            result["in_transit_last"] = len(in_transit)
            result["waiting_last"] = len(waiting)
            result["unfinished_at_horizon"] = len(dispatched - finished)
            result["unfinished_overdue"] = sum(
                task.sla_deadline < env.current_time for task in dispatched - finished
            )
            result["total_reported_carbon_kg"] = (
                result["facility_carbon_kg"] + result["network_carbon_kg"]
            )
            result["total_reported_cost_usd"] = (
                result["facility_cost_usd"] + result["network_cost_usd"]
            )
            result["sla_rate_completed_only"] = (
                result["sla_violated"] / len(finished) if finished else None
            )
            for key, value in result.items():
                if isinstance(value, float) and not math.isfinite(value):
                    raise AssertionError(f"Non-finite result {key}: {value}")
            return result
        finally:
            close = getattr(env, "close", None)
            if callable(close):
                close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--drain-steps", type=int, default=24)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42])
    parser.add_argument("--policies", nargs="+", choices=SpatialPolicy.NAMES,
                        default=list(SpatialPolicy.NAMES))
    parser.add_argument("--output", type=Path,
                        default=ROOT / "research_sci/results/pilot.json")
    args = parser.parse_args()
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("Use one or more unique seeds")
    if not args.policies or len(set(args.policies)) != len(args.policies):
        parser.error("Use one or more unique policies")
    rows = []
    for seed in args.seeds:
        for policy in args.policies:
            row = run_once(policy, seed, args.steps, args.drain_steps)
            rows.append(row)
            print(json.dumps({
                "seed": seed, "policy": policy,
                "carbon_kg": row["total_reported_carbon_kg"],
                "completed": row["tasks_finished"],
                "unfinished": row["unfinished_at_horizon"],
                "overdue": row["unfinished_overdue"],
            }), flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, allow_nan=False), encoding="utf-8")
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Raw results: {args.output} and {csv_path}")
    print("CAUTION: Pilot only. This is not a journal-quality comparison; unfinished tasks remain explicitly counted.")


if __name__ == "__main__":
    main()
