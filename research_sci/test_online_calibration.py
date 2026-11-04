"""Leakage, warmup and risk-margin contract tests for online calibration."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research_sci.online_calibration import OnlineResidualCalibrator
from research_sci.queue_risk import QueueRiskCarbonPolicy
from research_sci.test_queue_risk import FakeDC, IdentityTask


class OnlineCalibratorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def feed(self, cal, residual, index):
        actual = self.now + timedelta(minutes=30 * (index + 1))
        predicted = actual - timedelta(minutes=residual)
        cal.observe_completed(object(), predicted, actual, observed_at=actual)

    def test_warmup_then_upper_residual(self):
        cal = OnlineResidualCalibrator(alpha=0.25, min_samples=3, window=5,
                                       fallback_minutes=30)
        self.assertEqual(cal.margin_minutes(), 30)
        for i, resid in enumerate([10, 45, 70]):
            self.feed(cal, resid, i)
        self.assertEqual(cal.margin_minutes(), 70)
        self.assertEqual(cal.observed_count, 3)

    def test_warmup_does_not_look_ahead(self):
        cal = OnlineResidualCalibrator(min_samples=2, fallback_minutes=30)
        self.feed(cal, 120, 0)
        self.assertEqual(cal.margin_minutes(), 30)
        self.feed(cal, 50, 1)
        self.assertEqual(cal.margin_minutes(), 120)

    def test_negative_errors_never_produce_negative_buffer(self):
        cal = OnlineResidualCalibrator(alpha=.5, min_samples=2,
                                       fallback_minutes=0)
        self.feed(cal, -60, 0)
        self.feed(cal, -20, 1)
        self.assertEqual(cal.margin_minutes(), 0)

    def test_duplicate_completion_not_allowed(self):
        cal = OnlineResidualCalibrator()
        task = object()
        cal.observe_completed(task, self.now, self.now, self.now)
        with self.assertRaises(AssertionError):
            cal.observe_completed(task, self.now, self.now, self.now)

    def test_future_completion_rejected(self):
        cal = OnlineResidualCalibrator()
        with self.assertRaises(AssertionError):
            cal.observe_completed(object(), self.now, self.now + timedelta(minutes=1),
                                  self.now)

    def test_observations_must_be_monotonic(self):
        cal = OnlineResidualCalibrator()
        cal.observe_completed(object(), self.now, self.now, self.now)
        with self.assertRaises(ValueError):
            cal.observe_completed(object(), self.now, self.now - timedelta(minutes=1),
                                  self.now - timedelta(minutes=1))

    def test_missing_prediction_no_training(self):
        cal = OnlineResidualCalibrator()
        cal.observe_completed(object(), None, self.now, self.now)
        self.assertEqual(cal.no_forecast_count, 1)
        self.assertEqual(cal.margin_minutes(), 30)
        self.assertEqual(cal.observed_count, 0)

    def test_calibrated_policy_changes_candidate_after_observed_errors(self):
        dirty = FakeDC(1, carbon=600, cores=2)
        green = FakeDC(2, carbon=100, cores=0)
        runner = IdentityTask("running", cpu=2)
        runner.finish_time = self.now + timedelta(minutes=30)
        green.running_tasks = [runner]
        dcs = {"dirty": dirty, "green": green}
        task = IdentityTask("t", deadline=self.now + timedelta(minutes=90))
        cluster = SimpleNamespace(
            cloud_provider="aws", get_dc_location=lambda dc_id: f"dc-{dc_id}")
        p = QueueRiskCarbonPolicy("queue_calibrated_carbon", delay_fn=lambda *args: 0)
        self.assertEqual(p.choose(task, dcs, self.now, cluster), (2, False))
        # Force small warmup for this deterministic unit test.
        p.calibrator.min_samples = 2
        for i in range(2):
            actual = self.now + timedelta(minutes=60 + 15 * i)
            p.calibrator.observe_completed(
                object(), actual - timedelta(minutes=80), actual, actual)
        # Green predicted finish at 45 min; after 80-min buffer it no longer
        # fits deadline. Dirty predicted finish at 30 min also misses buffer,
        # so choose earliest completion instead.
        self.assertEqual(p.choose(task, dcs, self.now, cluster), (1, False))
        self.assertGreaterEqual(p.calibration_ready_decisions, 1)

    def test_calibrated_names_are_distinct(self):
        self.assertIn("queue_calibrated_carbon", QueueRiskCarbonPolicy.NAMES)
        self.assertIn("queue_calibrated_defer", QueueRiskCarbonPolicy.NAMES)
        self.assertIsNone(QueueRiskCarbonPolicy("queue_risk_carbon", delay_fn=lambda *a: 0).calibrator)


if __name__ == "__main__":
    unittest.main()
