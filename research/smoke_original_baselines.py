"""Short, non-publication smoke test of original SustainCluster rule baselines.

Runs each policy through the REAL environment and records simulator-derived
metrics. This is deliberately a short system integration smoke test, not a
statistical comparison or paper result. It does not use policy reward as
a substitute for physical carbon/cost measurements.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import tempfile

import yaml

from train_SAC_agent import make_env


POLICIES = ("lowest_carbon", "lowest_price", "round_robin")
ROOT = Path(__file__).resolve().parents[1]


def run_policy(policy: str, seed: int, steps: int) -> dict:
    cfg_path = ROOT / "configs/env/sim_config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf8"))
    cfg = copy.deepcopy(cfg)
    sim = cfg["simulation"]
    sim["strategy"] = policy
    sim["use_tensorboard"] = False
    sim["shuffle_datacenters"] = False
    # Rule strategies handle their own dispatch; the action to env.step()
    # is therefore only a placeholder when there are no agent-owned tasks.
    sim["single_action_mode"] = True
    sim["disable_defer_action"] = True

    with tempfile.TemporaryDirectory() as workdir:
        custom_cfg = Path(workdir) / "sim_config.yaml"
        custom_cfg.write_text(yaml.safe_dump(cfg), encoding="utf8")
        env = make_env(
            str(custom_cfg),
            str(ROOT / "configs/env/datacenters.yaml"),
            str(ROOT / "configs/env/reward_config.yaml"),
            writer=None,
            logger=None,
        )
        env.reset(seed=seed)
        result = {
            "policy": policy, "seed": seed, "steps_requested": steps,
            "steps_completed": 0,
            "energy_cost_usd": 0.0,
            "carbon_emissions_kg": 0.0,
            "energy_consumption_kwh": 0.0,
            "tasks_assigned": 0,
            "tasks_finished": 0,
            "sla_met": 0,
            "sla_violated": 0,
            "pending_last": 0,
        }
        for _ in range(steps):
            _, _, terminated, truncated, info = env.step(0)
            result["steps_completed"] += 1
            pending = 0
            for dc_data in info["datacenter_infos"].values():
                common = dc_data["__common__"]
                result["energy_cost_usd"] += float(common["energy_cost_USD"])
                result["carbon_emissions_kg"] += float(common["carbon_emissions_kg"])
                result["energy_consumption_kwh"] += float(common["energy_consumption_kwh"])
                result["tasks_assigned"] += int(common["tasks_assigned"])
                result["tasks_finished"] += int(common["finished_tasks_count"])
                result["sla_met"] += int(common["__sla__"]["met"])
                result["sla_violated"] += int(common["__sla__"]["violated"])
                pending += int(common["pending_tasks"])
            result["pending_last"] = pending
            if terminated or truncated:
                break
        close = getattr(env, "close", None)
        if callable(close):
            close()
        assert result["steps_completed"] == steps, result
        assert result["tasks_assigned"] >= result["tasks_finished"], result
        assert result["sla_met"] + result["sla_violated"] == result["tasks_finished"], result
        assert result["energy_cost_usd"] >= 0, result
        assert result["carbon_emissions_kg"] >= 0, result
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "research/results/smoke_baselines.json")
    args = parser.parse_args()
    if args.steps <= 0:
        parser.error("--steps must be positive")
    results = [run_policy(name, args.seed, args.steps) for name in POLICIES]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
