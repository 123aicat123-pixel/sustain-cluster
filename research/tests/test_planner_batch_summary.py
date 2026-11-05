"""Batch summaries retain timing metrics without importing heavy simulator deps."""
import ast
from pathlib import Path
import statistics
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "batch_unified_baselines.py"


def load_real_summary():
    """Execute only the actual METRICS declaration and pure summarize function."""
    tree = ast.parse(SOURCE.read_text(encoding="utf8"))
    metrics = next(node for node in tree.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "METRICS"
                           for t in node.targets))
    summary = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef)
                   and node.name == "summarize")
    module = ast.fix_missing_locations(ast.Module(
        body=[metrics, summary], type_ignores=[]
    ))
    namespace = {"statistics": statistics}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["METRICS"], namespace["summarize"]


class PlannerBatchSummaryTests(unittest.TestCase):
    def test_latency_and_budget_metrics_exported(self):
        metrics, summarize = load_real_summary()
        expected = (
            "planner_dispatch_p50_ms", "planner_dispatch_p95_ms",
            "planner_dispatch_ms_per_task", "planner_dispatch_calls",
            "nsga2_evaluation_requests",
        )
        for key in expected:
            self.assertIn(key, metrics)
        rows = [
            {"policy": "queue_nsga2", "planner_dispatch_p50_ms": 2.0,
             "planner_dispatch_p95_ms": 8.0,
             "planner_dispatch_ms_per_task": 0.7,
             "planner_dispatch_calls": 16, "nsga2_evaluation_requests": 6400},
            {"policy": "queue_nsga2", "planner_dispatch_p50_ms": 4.0,
             "planner_dispatch_p95_ms": 10.0,
             "planner_dispatch_ms_per_task": 0.9,
             "planner_dispatch_calls": 16, "nsga2_evaluation_requests": 6400},
        ]
        report = summarize(rows)["queue_nsga2"]["metrics"]
        self.assertAlmostEqual(report["planner_dispatch_p50_ms"]["mean"], 3.0)
        self.assertAlmostEqual(report["planner_dispatch_p95_ms"]["mean"], 9.0)
        self.assertAlmostEqual(report["planner_dispatch_ms_per_task"]["mean"], 0.8)
        self.assertEqual(report["nsga2_evaluation_requests"]["min"], 6400)

    def test_old_rows_without_timing_fields_are_not_silent_zeros(self):
        _, summarize = load_real_summary()
        report = summarize([{"policy": "legacy", "sla_violated": 1}])
        self.assertIsNone(report["legacy"]["metrics"]["planner_dispatch_p95_ms"]["mean"])


if __name__ == "__main__":
    unittest.main()
