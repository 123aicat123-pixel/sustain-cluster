"""Run native RBC selectors through the same per-task routing path as learned agents.

Research integration scaffold; not a publication-ready performance benchmark.
By setting strategy=manual_rl, single_action_mode=False, disable_defer_action=False,
all policies create *per-task actions* and pass through TaskSchedulingEnv.step(),
including its in-transit delay handling. We deliberately keep upstream
simulator and RBC implementation unchanged, and label this as an adapted RBC
comparison rather than a reproduction of the native immediate-routing mode.

Run: python -m research.unified_baseline_smoke --steps 16 --seed 42
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import tempfile
from pathlib import Path

import numpy as np
import yaml

from train_SAC_agent import make_env
from research.lifecycle_audit import audit_lifecycle
from research.task_sla_audit import analyze_finished_tasks
from research.sla_carbon_policy import SLAFeasibleCarbonPolicy
from utils.task_assignment_strategies import (
    DistributeRoundRobin, DistributeLowestCarbon, DistributeLowestPrice,
    DistributeMostAvailable, DistributeLeastPending,
)

ROOT = Path(__file__).resolve().parents[1]
POLICIES = {
    "lowest_carbon": DistributeLowestCarbon,
    "lowest_price": DistributeLowestPrice,
    "round_robin": DistributeRoundRobin,
    "most_available": DistributeMostAvailable,
    "least_pending": DistributeLeastPending,
    "sla_feasible_carbon": SLAFeasibleCarbonPolicy,
    "edf_sla_carbon": SLAFeasibleCarbonPolicy,
}


def choose_actions(policy, tasks, datacenters):
    """Adapt numeric DC IDs returned by upstream policies to 1-based action slots.

    All policies use one explicit fallback when the original selector returns
    None: route to task origin (or smallest-id DC if origin is missing).
    Do not claim that this fallback is the same as original RBC behavior.
    """
    dcs = list(datacenters.values())
    if not dcs:
        if tasks:
            raise ValueError("No data centers available for nonempty task list")
        return [], 0
    id_to_action = {dc.dc_id: idx + 1 for idx, dc in enumerate(dcs)}
    if len(id_to_action) != len(dcs):
        raise ValueError("Duplicate numerical DC IDs")
    first_id = min(id_to_action)
    actions = []
    fallbacks = 0
    for task in tasks:
        selected = policy(task, datacenters, logger=None)
        if selected not in id_to_action:
            fallbacks += 1
            selected = task.origin_dc_id if task.origin_dc_id in id_to_action else first_id
        actions.append(id_to_action[selected])
    assert len(actions) == len(tasks)
    return actions, fallbacks


def run(policy_name, seed, steps, drain_steps=0, completed_records=None):
    if policy_name not in POLICIES:
        raise ValueError(f"Unknown baseline: {policy_name}")
    if steps < 1 or drain_steps < 0 or steps + drain_steps > 7 * 24 * 4:
        raise ValueError("steps must be positive, drain nonnegative, total <= 672")
    # Current trace loader uses module-level PRNGs. Reseed before each policy to
    # avoid contamination from the preceding policy's random suffixes.
    random.seed(seed)
    np.random.seed(seed)
    config = copy.deepcopy(yaml.safe_load(
        (ROOT / "configs/env/sim_config.yaml").read_text(encoding="utf8")
    ))
    sim = config["simulation"]
    sim.update({
        "strategy": "manual_rl", "single_action_mode": False,
        "disable_defer_action": False, "shuffle_datacenters": False,
        "use_tensorboard": False,
    })
    with tempfile.TemporaryDirectory() as temp:
        cfgpath = Path(temp) / "sim_config.yaml"
        cfgpath.write_text(yaml.safe_dump(config), encoding="utf8")
        env = make_env(
            str(cfgpath), str(ROOT / "configs/env/datacenters.yaml"),
            str(ROOT / "configs/env/reward_config.yaml"),
            writer=None, logger=None,
        )
        assert env.single_action_mode is False
        assert env.disable_defer_action is False
        assert env.cluster_manager.strategy == "manual_rl"
        env.reset(seed=seed)
        # Prevent fresh admissions after a fixed horizon, without modifying
        # upstream data loaders or reward/environment physics. Drain can then
        # finish already-admitted tasks under a COMMON cutoff for all policies.
        if drain_steps:
            cutoff = env.start_time + env.time_step * steps
            upstream_loader = env.cluster_manager.get_tasks_for_timestep
            def admitted_only(time):
                return [] if time >= cutoff else upstream_loader(time)
            env.cluster_manager.get_tasks_for_timestep = admitted_only
        policy = POLICIES[policy_name]()
        policy.reset()
        summary = {
            "policy": policy_name, "routing": "shared_in_transit",
            "seed": seed, "steps_requested": steps, "steps_completed": 0,
            "admission_steps": steps, "drain_steps": drain_steps,
            "tasks_seen": 0, "tasks_dispatched": 0,
            "tasks_started": 0, "tasks_finished": 0,
            "sla_met": 0, "sla_violated": 0,
            "fallback_assignments": 0,
            "facility_energy_kwh": 0.0,
            "facility_cost_usd": 0.0,
            "facility_carbon_kg": 0.0,
            "transmission_cost_usd": 0.0,
            "transmission_energy_kwh": 0.0,
            "transmission_carbon_kg": 0.0,
            "pending_last": 0, "running_last": 0,
            "in_transit_last": 0, "undispatched_at_horizon": 0,
        }
        seen = set()
        dispatched = set()
        finished = set()
        for _ in range(steps + drain_steps):
            if policy_name == "edf_sla_carbon":
                # EDF is a priority rule, not just a destination rule: modifying
                # the task order changes arrival order in shared DC queues.
                env.current_tasks.sort(key=lambda t: (t.sla_deadline, t.arrival_time))
            tasks = list(env.current_tasks)
            for task in tasks:
                seen.add(task)
            if hasattr(policy, "set_context"):
                policy.set_context(env.current_time, env.cluster_manager)
            acts, fallbacks = choose_actions(
                policy, tasks, env.cluster_manager.datacenters
            )
            summary["fallback_assignments"] += fallbacks
            dispatched.update(tasks)
            _, _, terminated, truncated, info = env.step(acts)
            summary["steps_completed"] += 1
            pending = 0
            for dc_info in info["datacenter_infos"].values():
                c = dc_info["__common__"]
                summary["facility_energy_kwh"] += float(c["energy_consumption_kwh"])
                summary["facility_cost_usd"] += float(c["energy_cost_USD"])
                summary["facility_carbon_kg"] += float(c["carbon_emissions_kg"])
                summary["tasks_started"] += int(c["tasks_assigned"])
                summary["tasks_finished"] += int(c["finished_tasks_count"])
                summary["sla_met"] += int(c["__sla__"]["met"])
                summary["sla_violated"] += int(c["__sla__"]["violated"])
                finished.update(c["tasks_finished_this_step_objects"])
                pending += int(c["pending_tasks"])
            summary["transmission_cost_usd"] += float(info["transmission_cost_total_usd"])
            # NB upstream info keys are misnamed: "total_energy_kwh" and
            # "total_emissions_kg" contain ONLY the transfer contributions.
            summary["transmission_energy_kwh"] += float(info["total_energy_kwh"])
            summary["transmission_carbon_kg"] += float(info["total_emissions_kg"])
            summary["pending_last"] = pending
            if terminated or truncated:
                break
        pending_tasks = [
            task for dc in env.cluster_manager.datacenters.values()
            for task in dc.pending_tasks
        ]
        running_tasks = [
            task for dc in env.cluster_manager.datacenters.values()
            for task in dc.running_tasks
        ]
        transit_tasks = [task for _, task, _ in env.in_transit_tasks]
        audit = audit_lifecycle(dispatched, finished, pending_tasks, running_tasks, transit_tasks)
        summary["lifecycle_conserved"] = True
        summary["unfinished_overdue_at_horizon"] = sum(
            task.sla_deadline < env.current_time
            for task in dispatched - finished
        )
        summary["remaining_observation_tasks"] = len(env.current_tasks)
        independent_sla, task_rows = analyze_finished_tasks(finished, env.current_time)
        assert independent_sla["task_audit_completed"] == summary["tasks_finished"]
        assert independent_sla["task_audit_violated"] == summary["sla_violated"]
        assert independent_sla["task_audit_completed"] - independent_sla["task_audit_violated"] == summary["sla_met"]
        summary.update(independent_sla)
        if completed_records is not None:
            for row in task_rows:
                completed_records.append({"policy": policy_name, "seed": seed, **row})
        summary["tasks_seen"] = len(seen)
        summary["tasks_dispatched"] = len(dispatched)
        summary["in_transit_last"] = len(env.in_transit_tasks)
        summary["running_last"] = sum(
            len(dc.running_tasks) for dc in env.cluster_manager.datacenters.values()
        )
        summary["undispatched_at_horizon"] = len(env.current_tasks)
        summary["unfinished_dispatched"] = len(dispatched - finished)
        summary["reported_total_cost_usd"] = (
            summary["facility_cost_usd"] + summary["transmission_cost_usd"]
        )
        summary["reported_total_carbon_kg"] = (
            summary["facility_carbon_kg"] + summary["transmission_carbon_kg"]
        )
        # At this stage these are accounting consistency checks, not scientific
        # proof that energy/carbon models match physical reality.
        assert summary["steps_completed"] == steps + drain_steps, summary
        assert summary["sla_met"] + summary["sla_violated"] == summary["tasks_finished"], summary
        assert summary["tasks_finished"] == len(finished), "duplicate completion counted"
        assert summary["tasks_finished"] <= summary["tasks_started"] <= len(dispatched), summary
        assert audit["dispatched"] == summary["tasks_dispatched"], summary
        assert audit["finished"] == summary["tasks_finished"], summary
        assert audit["pending"] == summary["pending_last"], summary
        assert audit["running"] == summary["running_last"], summary
        assert audit["in_transit"] == summary["in_transit_last"], summary
        assert summary["tasks_started"] == summary["tasks_finished"] + summary["running_last"], summary
        assert summary["tasks_dispatched"] == summary["tasks_finished"] + summary["pending_last"] + summary["running_last"] + summary["in_transit_last"], summary
        if drain_steps:
            assert not env.current_tasks, "new tasks still admitted after cutoff"
        for key in (
            "facility_energy_kwh", "facility_cost_usd", "facility_carbon_kg",
            "transmission_cost_usd", "transmission_energy_kwh",
            "transmission_carbon_kg",
        ):
            assert np.isfinite(summary[key]), (key, summary)
            assert summary[key] >= -1e-8, (key, summary)
        close = getattr(env, "close", None)
        if callable(close):
            close()
        return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=16)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--drain-steps", type=int, default=0)
    p.add_argument(
        "--policies", nargs="+", choices=sorted(POLICIES), 
        default=["lowest_carbon", "lowest_price", "round_robin"]
    )
    p.add_argument("--output", type=Path, default=ROOT / "research/results/unified_baseline_smoke.json")
    args = p.parse_args()
    out = [run(policy, args.seed, args.steps, drain_steps=args.drain_steps) for policy in args.policies]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf8")
    print(json.dumps(out, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
