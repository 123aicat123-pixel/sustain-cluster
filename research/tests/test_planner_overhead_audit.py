"""Require complete, matched task cohorts for planner timing comparisons."""
import unittest

from research.planner_overhead_audit import audit_planner_rows


def row(policy, requests):
    return {
        "policy": policy, "seed": 901, "scenario_start_month": 5,
        "scenario_start_day": 19, "cpu_capacity_scale": 0.05,
        "tasks_dispatched": 20, "tasks_finished": 20,
        "unfinished_dispatched": 0, "fallback_assignments": 0,
        "fully_drained": True, "lifecycle_conserved": True,
        "planner_dispatch_calls": 2, "planner_dispatched_tasks": 20,
        "planner_dispatch_seconds": 0.02,
        "planner_dispatch_mean_ms": 10.0, "planner_dispatch_p50_ms": 5.0,
        "planner_dispatch_p95_ms": 15.0, "planner_dispatch_max_ms": 15.0,
        "planner_dispatch_ms_per_task": 1.0,
        "nsga2_evaluation_requests": requests,
    }


class PlannerOverheadAuditTests(unittest.TestCase):
    def setUp(self):
        self.rows = [row("queue_nsga2", 400), row("queue_nsga2_with_transit", 400)]

    def test_matched_complete(self):
        report = audit_planner_rows(self.rows)
        self.assertEqual(len(report), 2)

    def test_mismatched_admissions_rejected(self):
        self.rows[1]["tasks_dispatched"] = 19
        with self.assertRaises(AssertionError):
            audit_planner_rows(self.rows)

    def test_censored_outcome_rejected(self):
        self.rows[1]["tasks_finished"] = 19
        self.rows[1]["unfinished_dispatched"] = 1
        with self.assertRaises(AssertionError):
            audit_planner_rows(self.rows)

    def test_fallback_rejected(self):
        self.rows[1]["fallback_assignments"] = 1
        with self.assertRaises(AssertionError):
            audit_planner_rows(self.rows)

    def test_mismatched_search_budget_rejected(self):
        self.rows[1]["nsga2_evaluation_requests"] = 350
        with self.assertRaises(AssertionError):
            audit_planner_rows(self.rows)

    def test_missing_timing_coverage_rejected(self):
        self.rows[1]["planner_dispatched_tasks"] = 19
        with self.assertRaises(AssertionError):
            audit_planner_rows(self.rows)


if __name__ == "__main__":
    unittest.main()
