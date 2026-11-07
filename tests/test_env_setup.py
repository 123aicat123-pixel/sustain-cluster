"""Smoke test that the environment honors configured action mode."""
import numpy as np
from train_rl_agent import make_env
from utils.config_loader import load_yaml


def test_environment_runs():
    sim_path = "configs/env/sim_config.yaml"
    dc_path = "configs/env/datacenters.yaml"
    reward_path = "configs/env/reward_config.yaml"

    sim_cfg = load_yaml(sim_path)["simulation"]
    env = make_env(sim_path, dc_path, reward_path, writer=None)
    obs, _ = env.reset(seed=123)

    assert env.single_action_mode == sim_cfg["single_action_mode"]
    assert env.disable_defer_action == sim_cfg["disable_defer_action"]
    if env.single_action_mode:
        assert isinstance(obs, np.ndarray)
        assert obs.shape == env.observation_space.shape
    else:
        assert isinstance(obs, list)
        if obs:
            assert isinstance(obs[0], (list, np.ndarray))
