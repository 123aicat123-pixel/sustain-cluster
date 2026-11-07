"""Unit tests for actual source of DatacenterClusterManager.distribute_workload.

Execute the unchanged method AST on cheap dummy objects. This avoids importing
expensive data-center simulator dependencies in the selector-level CI.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[2] / "simulation/cluster_manager.py"


def get_actual_dispatch_method():
    source = ast.parse(SOURCE.read_text(encoding="utf8"))
    cls = next(n for n in source.body if isinstance(n, ast.ClassDef)
               and n.name == "DatacenterClusterManager")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == "distribute_workload")
    mod = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    symbols = {}
    exec(compile(mod, str(SOURCE), "exec"), symbols)
    return symbols["distribute_workload"]


class TestDispatchFailureHandling(unittest.TestCase):
    def setUp(self):
        self.dispatch = get_actual_dispatch_method()
        self.task = SimpleNamespace(job_name="test-task", dest_dc=None, dest_dc_id=None)
        self.warnings = []
        self.logger = SimpleNamespace(warning=self.warnings.append)

    def test_no_feasible_dc_returns_none_instead_of_crashing(self):
        manager = SimpleNamespace(
            strategy="lowest_carbon",
            datacenters={"DC1": SimpleNamespace(dc_id=1)},
            strategy_map={"lowest_carbon": lambda task, dcs, log: None},
        )
        result = self.dispatch(manager, self.task, "2026-01-01", self.logger)
        self.assertIsNone(result)
        self.assertIsNone(self.task.dest_dc_id)
        self.assertTrue(self.warnings)

    def test_valid_assignment_updates_destination(self):
        dest = SimpleNamespace(dc_id=2)
        manager = SimpleNamespace(
            strategy="lowest_carbon",
            datacenters={"DC2": dest},
            strategy_map={"lowest_carbon": lambda task, dcs, log: 2},
        )
        result = self.dispatch(manager, self.task, "2026-01-01", self.logger)
        self.assertEqual(result, 2)
        self.assertEqual(self.task.dest_dc_id, 2)
        self.assertIs(self.task.dest_dc, dest)

    def test_stale_destination_id_is_rejected(self):
        manager = SimpleNamespace(
            strategy="lowest_price",
            datacenters={"DC1": SimpleNamespace(dc_id=1)},
            strategy_map={"lowest_price": lambda task, dcs, log: 999},
        )
        self.assertIsNone(self.dispatch(manager, self.task, "2026-01-01", None))

    def test_manual_rl_returns_none_without_selector_call(self):
        manager = SimpleNamespace(strategy="manual_rl")
        self.assertIsNone(self.dispatch(manager, self.task, "2026-01-01", None))


if __name__ == "__main__":
    unittest.main()
