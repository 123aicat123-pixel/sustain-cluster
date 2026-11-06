"""Tests counterbalanced equivalence without invoking the simulator."""
import unittest
from research.indexed_order_audit import audit_counterbalanced, LEGACY, INDEXED


def run(policy):
    return {
        "policy": policy, "seed": 901,
        "scenario_start_month": 5, "scenario_start_day": 19,
        "cpu_capacity_scale": 0.05, "tasks_dispatched": 1,
        "tasks_finished": 1, "unfinished_dispatched": 0,
        "fallback_assignments": 0, "fully_drained": True,
        "lifecycle_conserved": True, "planner_dispatch_calls": 1,
        "planner_dispatched_tasks": 1, "planner_dispatch_seconds": 0.01,
        "planner_dispatch_mean_ms": 10, "planner_dispatch_p50_ms": 10,
        "planner_dispatch_p95_ms": 10, "planner_dispatch_max_ms": 10,
        "planner_dispatch_ms_per_task": 10,
        "planner_projection_seconds": 0.005, "nsga2_evaluation_requests": 400,
        "sla_violated": 0, "reported_total_carbon_kg": 100,
        "reported_total_cost_usd": 12, "forecast_mae_minutes": 0,
    }


def task(policy):
    return {
        "policy": policy, "seed": 901,
        "arrival_utc": "2020-05-19T00:00:00+00:00", "job_name": "task",
        "duration_minutes": "30", "deadline_utc": "2020-05-19T01:00:00+00:00",
        "origin_dc_id": "1", "dest_dc_id": "2",
        "start_utc": "2020-05-19T00:15:00+00:00",
        "finish_utc": "2020-05-19T00:45:00+00:00",
        "sla_met": "True",
    }


class IndexedOrderAuditTests(unittest.TestCase):
    def setUp(self):
        self.results = {
            "forward": [run(LEGACY), run(INDEXED)],
            "reverse": [run(INDEXED), run(LEGACY)],
        }
        self.tasks = {
            "forward": [task(LEGACY), task(INDEXED)],
            "reverse": [task(INDEXED), task(LEGACY)],
        }

    def test_equal_across_orders_with_signed_timing(self):
        self.results["forward"][1]["planner_dispatch_p95_ms"] = 9
        self.results["forward"][1]["planner_dispatch_max_ms"] = 10
        self.results["reverse"][0]["planner_dispatch_p95_ms"] = 9
        out = audit_counterbalanced(self.results, self.tasks)
        self.assertTrue(out[0]["exact_task_level_equality"])
        self.assertEqual(out[0]["orders"]["forward"]["p95_delta_ms"], -1)

    def test_detect_reverse_task_drift(self):
        self.tasks["reverse"][0]["dest_dc_id"] = "3"
        with self.assertRaises(AssertionError):
            audit_counterbalanced(self.results, self.tasks)

    def test_reject_missing_order(self):
        with self.assertRaises(AssertionError):
            audit_counterbalanced({"forward": self.results["forward"]}, self.tasks)

    def test_reject_censored_run(self):
        self.results["reverse"][0]["tasks_finished"] = 0
        with self.assertRaises(AssertionError):
            audit_counterbalanced(self.results, self.tasks)


if __name__ == "__main__":
    unittest.main()
