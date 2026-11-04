"""No-simulator tests for strictly pre-decision resource pressure audit."""
import unittest
from datetime import datetime, timedelta, timezone

from research_sci.state_risk_audit import (
    snapshot_decision, state_bands, audit_state_risk,
)
from research_sci.test_queue_risk import FakeDC, IdentityTask


class PressureAuditTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.task = IdentityTask(
            "new-task", duration=20, cpu=1,
            deadline=self.now + timedelta(hours=3))
        self.dc = FakeDC(1, cores=1)
        self.dc.total_cores = 2
        self.dc.total_gpus = 1
        self.dc.total_mem_GB = 100
        self.dc.available_gpus = 1
        self.dc.available_mem = 100

    def snapshot(self, task=None, pred=None, inbound=()):
        task = task or self.task
        return snapshot_decision(
            task, self.dc, self.now,
            self.now + timedelta(minutes=40) if pred is None else pred,
            inbound
        )

    def test_only_observable_features_at_dispatch(self):
        self.task.finish_time = self.now + timedelta(days=1)
        state = self.snapshot()
        self.assertEqual(state["cpu_util_fraction"], .5)
        self.assertEqual(state["current_pending"], 0)
        self.assertEqual(state["known_inbound"], 0)
        self.assertEqual(state["predicted_sla_slack_minutes"], 140)
        self.assertNotIn("actual_finish", state)
        self.assertNotIn("actual_met_sla", state)
        self.assertNotIn("forecast_error_minutes", state)

    def test_known_inbound_and_queue_pressure(self):
        prior = IdentityTask("prior", duration=30, cpu=2)
        self.dc.pending_tasks = [prior]
        state = self.snapshot(inbound=[(self.now + timedelta(minutes=15), prior)])
        self.assertEqual(state["known_inbound"], 1)
        self.assertEqual(state["known_inbound_core_minutes"], 60)
        self.assertEqual(state["pending_core_minutes"], 60)
        self.assertEqual(state_bands(state)["pending_queue"], "pending")
        self.assertEqual(state_bands(state)["committed_inbound"], "inbound")

    def test_duplicate_target_in_commitments_is_rejected(self):
        with self.assertRaises(AssertionError):
            self.snapshot(inbound=[(self.now, self.task)])

    def test_outcome_only_joined_after_completion(self):
        one = self.task
        two = IdentityTask("censored", duration=20, cpu=1,
                           deadline=self.now + timedelta(hours=3))
        observations = {one: self.snapshot(one), two: self.snapshot(two)}
        one.finish_time = self.now + timedelta(minutes=95)
        two.finish_time = self.now + timedelta(days=100)
        report, rows = audit_state_risk(observations, {one})
        self.assertEqual(report["total"]["completed"], 1)
        self.assertEqual(report["total"]["censored_unfinished"], 1)
        self.assertEqual(report["total"]["forecast_evaluable"], 1)
        self.assertAlmostEqual(report["total"]["forecast_mae_minutes"], 55)
        censored = next(row for row in rows if row["task_name"] == "censored")
        self.assertIsNone(censored["actual_finish"])
        self.assertIsNone(censored["forecast_error_minutes"])

    def test_missing_prediction_and_undefined_rates_are_explicit(self):
        state = snapshot_decision(self.task, self.dc, self.now, None, [])
        report, rows = audit_state_risk({self.task: state}, set())
        self.assertEqual(report["total"]["forecast_missing"], 1)
        self.assertIsNone(report["total"]["forecast_mae_minutes"])
        self.assertEqual(state_bands(state)["predicted_sla_slack"], "no_forecast")

    def test_invalid_resource_capacity_does_not_silently_clamp(self):
        self.dc.available_cores = 4
        with self.assertRaises(ValueError):
            self.snapshot()


if __name__ == "__main__":
    unittest.main()
