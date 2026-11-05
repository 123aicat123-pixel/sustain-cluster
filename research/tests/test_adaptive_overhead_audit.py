"""Adaptive timing audit reports negative outcomes instead of censoring them."""
import unittest

from research.adaptive_overhead_audit import compare_adaptive_runs


def row(policy):
    return {
        "policy": policy, "seed": 901, "scenario_start_month": 6,
        "scenario_start_day": 15, "cpu_capacity_scale": 0.05,
        "tasks_dispatched": 20, "tasks_finished": 20,
        "unfinished_dispatched": 0, "fallback_assignments": 0,
        "fully_drained": True, "lifecycle_conserved": True,
        "planner_dispatch_calls": 2, "planner_dispatched_tasks": 20,
        "planner_dispatch_seconds": 0.02,
        "planner_dispatch_mean_ms": 10.0, "planner_dispatch_p50_ms": 5.0,
        "planner_dispatch_p95_ms": 15.0, "planner_dispatch_max_ms": 15.0,
        "planner_dispatch_ms_per_task": 1.0,
        "nsga2_evaluation_requests": 400,
        "sla_violated": 2, "reported_total_carbon_kg": 100,
        "reported_total_cost_usd": 10, "forecast_mae_minutes": 1.5,
        "adaptive_projection_checks": 0, "adaptive_base_projections": 0,
        "adaptive_transit_projections": 0,
    }


class AdaptiveAuditTests(unittest.TestCase):
    def setUp(self):
        self.base = row("queue_nsga2_with_transit")
        self.adapt = row("queue_nsga2_adaptive_transit")
        self.adapt.update(adaptive_projection_checks=10,
                          adaptive_base_projections=7,
                          adaptive_transit_projections=3)

    def test_report_regression_without_discarding_it(self):
        self.adapt["sla_violated"] = 4
        self.adapt["reported_total_carbon_kg"] = 101
        result = compare_adaptive_runs([self.base, self.adapt])[0]
        self.assertEqual(result["sla_misses_delta"], 2)
        self.assertEqual(result["carbon_kg_delta"], 1)
        self.assertAlmostEqual(result["adaptive_skip_fraction"], 0.7)

    def test_missing_adaptive_counts_rejected(self):
        self.adapt["adaptive_transit_projections"] = 4
        with self.assertRaises(AssertionError):
            compare_adaptive_runs([self.base, self.adapt])

    def test_incomplete_task_cohort_rejected(self):
        self.adapt["tasks_finished"] = 19
        with self.assertRaises(AssertionError):
            compare_adaptive_runs([self.base, self.adapt])

    def test_search_budget_mismatch_rejected(self):
        self.adapt["nsga2_evaluation_requests"] = 399
        with self.assertRaises(AssertionError):
            compare_adaptive_runs([self.base, self.adapt])


if __name__ == "__main__":
    unittest.main()
