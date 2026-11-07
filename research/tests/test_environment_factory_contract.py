"""Guard the training factory's simulation configuration forwarding.

AST-based so the small research CI can check the contract without installing
PyTorch/Gym or loading a workload. Full behavioral simulation still required.
"""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class TestEnvironmentFactoryContract(unittest.TestCase):
    def test_make_env_forwards_simulation_settings(self):
        tree = ast.parse((ROOT / "train_rl_agent.py").read_text(encoding="utf8"))
        factory = next(
            x for x in tree.body
            if isinstance(x, ast.FunctionDef) and x.name == "make_env"
        )
        constructors = [
            call for call in ast.walk(factory)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "TaskSchedulingEnv"
        ]
        self.assertEqual(len(constructors), 1)
        call = constructors[0]
        kwargs = {k.arg: k.value for k in call.keywords}
        self.assertIn("sim_config", kwargs)
        self.assertIsInstance(kwargs["sim_config"], ast.Name)
        self.assertEqual(kwargs["sim_config"].id, "sim_cfg")

    def test_default_yaml_requests_single_action_without_deferral(self):
        # Characterize the upstream baseline settings (no PyYAML needed).
        content = (ROOT / "configs/env/sim_config.yaml").read_text(encoding="utf8")
        self.assertIn("disable_defer_action: true", content)
        self.assertIn("single_action_mode: true", content)


if __name__ == "__main__":
    unittest.main()
