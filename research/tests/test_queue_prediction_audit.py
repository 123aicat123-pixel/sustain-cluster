"""Forecast accuracy is independently checked from immutable time records."""
import unittest
from datetime import datetime,timedelta,timezone

from research.queue_prediction_audit import audit_forecasts


def make_task(name,actual,origin,dest):
    item=type("DummyTask",(),{})()
    item.job_name=name
    item.arrival_time=actual-timedelta(minutes=30)
    item.start_time=actual
    item.duration=10
    item.finish_time=actual+timedelta(minutes=10)
    item.sla_deadline=actual+timedelta(minutes=5)
    item.origin_dc_id=origin
    item.dest_dc_id=dest
    return item


class TestStartPredictionAudit(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.a=make_task("A",self.now+timedelta(minutes=15),1,1)
        self.b=make_task("B",self.now+timedelta(minutes=30),1,2)

    def test_residuals_mae_p95_and_remote_split(self):
        metrics,rows=audit_forecasts(
            [self.a,self.b],
            {
                self.a:self.now,
                self.b:self.now+timedelta(minutes=45)
            },
            seed=137,policy="queue"
        )
        self.assertEqual(metrics["forecast_count"],2)
        self.assertEqual(metrics["forecast_mae_minutes"],15)
        self.assertEqual(metrics["forecast_p95_abs_minutes"],15)
        self.assertEqual(metrics["forecast_bias_minutes"],0)
        self.assertEqual(metrics["forecast_overoptimistic_fraction"],.5)
        self.assertEqual(metrics["forecast_remote_mae_minutes"],15)
        self.assertEqual(metrics["forecast_local_mae_minutes"],15)
        self.assertTrue(any(r["is_remote"] for r in rows))
        self.assertEqual({r["arrival_utc"] for r in rows},
                         {self.a.arrival_time.isoformat(), self.b.arrival_time.isoformat()})
        self.assertEqual(metrics["forecast_false_safe_count"],1)
        self.assertEqual(metrics["forecast_actual_sla_misses"],2)
        self.assertEqual(metrics["forecast_predicted_sla_misses"],1)
        self.assertEqual(metrics["forecast_sla_confusion_counts"]["pred_met_actual_miss"],1)

    def test_missing_forecast_is_fatal(self):
        with self.assertRaisesRegex(AssertionError,"lacks"):
            audit_forecasts([self.a],{},seed=1,policy="x")

    def test_empty_completion_batch(self):
        metrics,rows=audit_forecasts([],{},seed=1,policy="x")
        self.assertEqual(metrics["forecast_count"],0)
        self.assertIsNone(metrics["forecast_mae_minutes"])
        self.assertFalse(rows)


if __name__=="__main__":
    unittest.main()
