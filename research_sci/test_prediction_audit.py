"""Unit tests of task-level forecast auditing and censoring behavior."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research_sci.prediction_audit import summarize_forecasts


class Task:
    def __init__(self, name, deadline, finish_time=None):
        self.job_name = name
        self.sla_deadline = deadline
        self.finish_time = finish_time


class PredictionAuditTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_completed_error_and_sla_false_safe(self):
        early = Task("early", self.now + timedelta(minutes=60),
                     self.now + timedelta(minutes=75))
        late = Task("late", self.now + timedelta(minutes=60),
                    self.now + timedelta(minutes=45))
        preds = {
            early: self.now + timedelta(minutes=45),
            late: self.now + timedelta(minutes=55),
        }
        metrics, rows = summarize_forecasts(preds, [early, late], buffer_minutes=15)
        self.assertEqual(metrics["forecast_completed_evaluable"], 2)
        self.assertEqual(metrics["forecast_false_safe_completed"], 1)
        self.assertEqual(metrics["forecast_predicted_safe_completed"], 2)
        self.assertEqual(metrics["forecast_error_above_buffer"], 1)
        self.assertAlmostEqual(metrics["forecast_signed_bias_minutes"], 10)
        self.assertAlmostEqual(metrics["forecast_mae_minutes"], 20)
        self.assertEqual(rows[0]["error_minutes"], 30)

    def test_unfinished_job_is_censored_even_if_finish_time_set(self):
        task = Task("running", self.now + timedelta(minutes=60),
                    self.now + timedelta(minutes=120))
        metrics, rows = summarize_forecasts(
            {task: self.now + timedelta(minutes=30)}, [])
        self.assertEqual(metrics["forecast_censored_unfinished"], 1)
        self.assertEqual(metrics["forecast_completed_evaluable"], 0)
        self.assertIsNone(metrics["forecast_mae_minutes"])
        self.assertIsNone(rows[0]["actual_finish"])
        self.assertIsNone(rows[0]["actual_met_sla"])

    def test_missing_prediction_separate_from_error(self):
        task = Task("unknown", self.now + timedelta(minutes=60),
                    self.now + timedelta(minutes=50))
        metrics, rows = summarize_forecasts({task: None}, [task])
        self.assertEqual(metrics["forecast_unavailable"], 1)
        self.assertEqual(metrics["forecast_completed_evaluable"], 0)
        self.assertIsNone(rows[0]["predicted_met_sla"])

    def test_no_records_has_defined_empty_summary(self):
        metrics, rows = summarize_forecasts({}, [])
        self.assertEqual(rows, [])
        self.assertIsNone(metrics["forecast_false_safe_rate"])
        self.assertEqual(metrics["forecast_records"], 0)

    def test_invalid_buffer_rejected(self):
        with self.assertRaises(ValueError):
            summarize_forecasts({}, [], buffer_minutes=-1)


if __name__ == "__main__":
    unittest.main()
