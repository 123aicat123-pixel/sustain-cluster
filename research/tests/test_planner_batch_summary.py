"""Batch summaries retain planner latency and fixed search budgets."""
import unittest

from research.batch_unified_baselines import METRICS, summarize


class PlannerBatchSummaryTests(unittest.TestCase):
    def test_latency_and_budget_metrics_exported(self):
        expected = (
            "planner_dispatch_p50_ms", "planner_dispatch_p95_ms",
            "planner_dispatch_ms_per_task", "planner_dispatch_calls",
            "nsga2_evaluation_requests",
        )
        for key in expected:
            self.assertIn(key, METRICS)
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
        report = summarize([{"policy": "legacy", "sla_violated": 1}])
        self.assertIsNone(report["legacy"]["metrics"]["planner_dispatch_p95_ms"]["mean"])


if __name__ == "__main__":
    unittest.main()
