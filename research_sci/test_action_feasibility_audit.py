"""Tests for all-DC pre-routing forecasts and explicit counterfactual limits."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research_sci.action_feasibility_audit import (
    evaluate_candidates, summarize_candidate_audit,
)
from research_sci.test_queue_risk import FakeDC, IdentityTask


class CandidateAuditTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.task=IdentityTask("candidate",duration=15,cpu=1,
                      deadline=self.now+timedelta(minutes=50))
        self.clean=FakeDC(1,carbon=100,cores=2)
        self.dirty=FakeDC(2,carbon=500,cores=2)
        self.dcs={"clean":self.clean,"dirty":self.dirty}
        self.cluster=SimpleNamespace(
            cloud_provider="aws",
            get_dc_location=lambda dc_id:f"dc-{dc_id}"
        )
        self.delay=lambda origin,dest,provider,bandwidth: 0

    def evaluate(self,chosen=1,commitments=None,buffer=30):
        return evaluate_candidates(
            self.task,self.dcs,self.now,self.cluster,
            commitments or {1:[],2:[]},chosen,step_seconds=900,
            buffer_minutes=buffer,delay_fn=self.delay
        )

    def test_all_candidates_no_future_labels(self):
        self.task.finish_time=self.now+timedelta(days=10)
        row=self.evaluate()
        self.assertEqual(row["total_dc_count"],2)
        self.assertEqual(row["forecastable_count"],2)
        self.assertEqual(row["unbuffered_feasible_count"],2)
        self.assertEqual(row["buffered_feasible_count"],1*0)
        self.assertTrue(row["any_unbuffered_feasible"])
        self.assertFalse(row["any_buffered_feasible"])
        self.assertNotIn("actual_finish",row)
        self.assertNotIn("actual_met_sla",row)

    def test_selected_late_but_alternative_has_predicted_slack(self):
        self.clean.available_cores=0
        busy=IdentityTask("busy",duration=100,cpu=2)
        busy.finish_time=self.now+timedelta(hours=3)
        self.clean.running_tasks=[busy]
        row=self.evaluate(chosen=1)
        self.assertFalse(row["selected_forecast_unbuffered_feasible"])
        self.assertEqual(row["unbuffered_feasible_count"],1)
        self.assertTrue(row["predicted_unbuffered_rescue_elsewhere"])
        self.assertEqual(row["lowest_intensity_feasible_dc_id"],2)
        summary,_=summarize_candidate_audit({self.task:row},set())
        self.assertEqual(summary["unbuffered_predicted_rescue_elsewhere"],1)
        self.assertEqual(summary["censored_unfinished"],1)
        self.assertEqual(summary["observed_sla_misses_completed"],0)

    def test_simulated_alternative_not_a_real_sla_rescue(self):
        self.clean.available_cores=0
        busy=IdentityTask("busy",duration=100,cpu=2)
        busy.finish_time=self.now+timedelta(hours=3)
        self.clean.running_tasks=[busy]
        row=self.evaluate(chosen=1)
        self.task.finish_time=self.now+timedelta(hours=4)
        report,rows=summarize_candidate_audit({self.task:row},{self.task})
        self.assertEqual(report["observed_sla_misses_completed"],1)
        self.assertEqual(report["unbuffered_predicted_rescue_and_actual_missed_completed"],1)
        self.assertFalse(rows[0]["actual_met_sla"])

    def test_reservation_can_remove_feasible_center(self):
        reservations={1:[],2:[(
            self.now+timedelta(minutes=15),
            IdentityTask("inbound",duration=100,cpu=2)
        )]}
        row=self.evaluate(chosen=2,commitments=reservations)
        self.assertEqual(row["unbuffered_feasible_count"],1)
        self.assertEqual(row["lowest_intensity_feasible_dc_id"],1)
        self.assertEqual(row["candidate_centers"][1]["known_inbound"],1)

    def test_delays_and_buffer_feasibility(self):
        self.task.sla_deadline=self.now+timedelta(minutes=90)
        row=self.evaluate(chosen=2,buffer=30)
        self.assertEqual(row["buffered_feasible_count"],2)
        self.assertTrue(row["predicted_buffered_rescue_elsewhere"] is False)
        self.assertFalse(row["selected_intensity_is_cheapest_buffered_feasible"])
        self.assertEqual(row["lowest_intensity_buffered_feasible_dc_id"],1)

    def test_reject_own_job_in_known_commitments(self):
        with self.assertRaises(AssertionError):
            self.evaluate(commitments={1:[(self.now,self.task)],2:[]})

    def test_unforecastable_all_centers_is_not_zero_risk(self):
        self.task.cores_req=10
        row=self.evaluate(chosen=1)
        self.assertEqual(row["forecastable_count"],0)
        self.assertFalse(row["any_unbuffered_feasible"])
        report,_=summarize_candidate_audit({self.task:row},set())
        self.assertEqual(report["no_candidate_forecast"],1)
        self.assertEqual(report["no_unbuffered_feasible_center"],1)

if __name__=="__main__":
    unittest.main()
