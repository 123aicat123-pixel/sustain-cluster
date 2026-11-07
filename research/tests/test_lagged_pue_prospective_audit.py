"""Prospective carbon/SLA audit must retain mixed and adverse outcomes."""
import unittest

from research.lagged_pue_prospective_audit import (
    CANDIDATE, HEURISTIC, REFERENCE, audit_prospective,
)


def run(policy, seed):
    return {
        "policy": policy, "seed": seed,
        "scenario_start_month": 1, "scenario_start_day": 20,
        "cpu_capacity_scale": 0.05,
        "tasks_dispatched": 1, "tasks_finished": 1,
        "unfinished_dispatched": 0, "fallback_assignments": 0,
        "fully_drained": True, "lifecycle_conserved": True,
        "planner_dispatch_calls": 1, "planner_dispatched_tasks": 1,
        "planner_dispatch_seconds": 0.01,
        "planner_dispatch_mean_ms": 10.0, "planner_dispatch_p50_ms": 10.0,
        "planner_dispatch_p95_ms": 10.0, "planner_dispatch_max_ms": 10.0,
        "planner_dispatch_ms_per_task": 10.0,
        "nsga2_evaluation_requests": 0 if policy == HEURISTIC else 400,
        "sla_violated": 0, "reported_total_carbon_kg": 100.0,
        "reported_total_cost_usd": 12.0,
        "facility_carbon_kg": 99.0, "transmission_carbon_kg": 1.0,
        "facility_cost_usd": 11.0, "transmission_cost_usd": 1.0,
        "steps_completed": 128,
        "lagged_pue_observation_steps": 128 if policy == CANDIDATE else 0,
        "lagged_pue_missing_site_readings": 0,
        "lagged_pue_nonunit_site_readings": 640 if policy == CANDIDATE else 0,
        "lagged_pue_max": 2.2 if policy == CANDIDATE else 1.0,
    }


def task(policy, seed):
    return {
        "policy": policy, "seed": seed, "arrival_utc": "2020-01-20T00:00:00Z",
        "job_name": "job", "origin_dc_id": "1", "dest_dc_id": "2",
        "duration_minutes": "15", "deadline_utc": "2020-01-20T01:00:00Z",
        "start_utc": "2020-01-20T00:15:00Z",
        "finish_utc": "2020-01-20T00:30:00Z", "sla_met": "True",
    }


class ProspectiveAuditTests(unittest.TestCase):
    def setUp(self):
        self.runs = [run(p, s) for s in (901, 1701)
                     for p in (REFERENCE, CANDIDATE, HEURISTIC)]
        self.tasks = [task(p, s) for s in (901, 1701)
                      for p in (REFERENCE, CANDIDATE, HEURISTIC)]

    def test_mixed_outcomes_are_retained(self):
        row = next(r for r in self.runs
                   if r["seed"] == 1701 and r["policy"] == CANDIDATE)
        row["reported_total_carbon_kg"] = 101
        row["facility_carbon_kg"] = 100
        report = audit_prospective(self.runs, self.tasks)
        self.assertEqual(len(report), 2)
        self.assertTrue(report[0]["joint_carbon_and_sla_nonworse"])
        self.assertFalse(report[1]["joint_carbon_and_sla_nonworse"])
        self.assertEqual(report[1]["realized_carbon_delta_kg"], 1)

    def test_unfinished_cohort_rejected(self):
        self.runs[1]["tasks_finished"] = 0
        with self.assertRaises(AssertionError):
            audit_prospective(self.runs, self.tasks)

    def test_missing_seed_rejected(self):
        with self.assertRaises(AssertionError):
            audit_prospective([r for r in self.runs if r["seed"] == 901],
                              [r for r in self.tasks if r["seed"] == 901])

    def test_budget_mismatch_rejected(self):
        next(r for r in self.runs if r["policy"] == CANDIDATE
             and r["seed"] == 901)["nsga2_evaluation_requests"] = 100
        with self.assertRaises(AssertionError):
            audit_prospective(self.runs, self.tasks)

    def test_task_mutation_rejected(self):
        next(r for r in self.tasks if r["policy"] == CANDIDATE
             and r["seed"] == 901)["deadline_utc"] = "2020-01-20T02:00:00Z"
        with self.assertRaises(AssertionError):
            audit_prospective(self.runs, self.tasks)


if __name__ == "__main__":
    unittest.main()
