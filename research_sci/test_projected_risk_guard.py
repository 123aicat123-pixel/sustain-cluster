"""No-simulator tests for batch-level projected-risk shadow safeguard."""
import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace

from research_sci.projected_risk_guard import ProjectedRiskGuard
from research_sci.test_queue_risk import IdentityTask,FakeDC
from research_sci.joint_batch import JointBatchCarbonPlanner


class ProjectedRiskGuardTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.a=FakeDC(1,carbon=100,cores=2)
        self.b=FakeDC(2,carbon=500,cores=2)
        self.dcs={"a":self.a,"b":self.b}
        self.manager=SimpleNamespace(
            get_dc_location=lambda i:f"dc-{i}",cloud_provider="aws"
        )
        self.delay=lambda *args:0
        self.task=IdentityTask(
            "test",duration=30,cpu=1,
            deadline=self.now+timedelta(hours=2)
        )
        self.known={1:[],2:[]}

    def guard(self,mode):
        return ProjectedRiskGuard(mode,risk_buffer_minutes=30,
                                  delay_fn=self.delay)

    def review(self,mode,prediction,route=1):
        return self.guard(mode).review(
            [self.task],self.dcs,self.now,self.manager,self.known,
            {"routes":[route],"predictions":[prediction]}
        )

    def test_strict_guard_rejects_any_later_finish(self):
        original=self.now+timedelta(minutes=45)
        response=self.review("guard0",original+timedelta(minutes=1))
        self.assertFalse(response["accepted"])
        self.assertEqual(response["reason"],"forecast_sla_regression")
        self.assertEqual(response["greedy_routes"],[1])
        self.assertEqual(response["predicted_late_beam"],0)

    def test_relaxed_guard_preserves_buffered_sla(self):
        # A 15-minute loss on the first job is permitted only because
        # a DIFFERENT job gains finish time; otherwise there is no
        # strict projected benefit and the proposal is rejected.
        second=IdentityTask(
            "second",duration=15,cpu=1,
            deadline=self.now+timedelta(hours=3)
        )
        first_finish=self.now+timedelta(minutes=45)
        second_finish=self.now+timedelta(minutes=30)
        def review(delay_minutes):
            return self.guard("guard15").review(
                [self.task,second],self.dcs,self.now,self.manager,self.known,
                {"routes":[1,1],"predictions":[
                    first_finish+timedelta(minutes=delay_minutes),
                    second_finish-timedelta(minutes=1)
                ]}
            )
        self.assertTrue(review(15)["accepted"])
        self.assertFalse(review(16)["accepted"])

    def test_guard_rejects_lower_carbon_for_buffer_violation(self):
        self.task.sla_deadline=self.now+timedelta(minutes=75)
        # Greedy slack=30 -> no allowable postponement with guard15.
        result=self.review("guard15",self.now+timedelta(minutes=46),route=2)
        self.assertFalse(result["accepted"])

    def test_strict_no_gain_rejects_same_route_and_finish(self):
        result=self.review("guard0",self.now+timedelta(minutes=45))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"],"no_strict_projected_gain")

    def test_strict_accepts_earlier_finish(self):
        result=self.review("guard0",self.now+timedelta(minutes=44))
        self.assertTrue(result["accepted"])

    def test_reject_unforecastable_instead_of_promising_rescue(self):
        impossible=IdentityTask("huge",duration=30,cpu=999,
                     deadline=self.now+timedelta(hours=3))
        r=self.guard("guard0").review(
            [impossible],self.dcs,self.now,self.manager,self.known,
            {"routes":[1],"predictions":[None]}
        )
        self.assertFalse(r["accepted"])
        self.assertEqual(r["reason"],"no_strict_projected_gain")

    def test_forced_origin_task_is_never_optimistically_accepted(self):
        self.task.sla_deadline=self.now-timedelta(minutes=1)
        r=self.review("guard0",self.now+timedelta(minutes=5))
        self.assertFalse(r["accepted"])
        self.assertEqual(r["reason"],"empty_or_forced_origin")

    def test_prediction_and_task_reservations_are_read_only(self):
        before={key:list(items) for key,items in self.known.items()}
        self.review("guard15",self.now+timedelta(minutes=45))
        self.assertEqual(self.known,before)
        self.assertEqual(self.a.pending_tasks,[])
        self.assertEqual(self.b.pending_tasks,[])

    def test_beam_proposal_can_be_reviewed_with_real_queue_predictor(self):
        urgent=IdentityTask("urgent",duration=15,cpu=1,
                      deadline=self.now+timedelta(hours=2))
        plan=JointBatchCarbonPlanner(
            beam_width=4,chunk_size=8,delay_fn=self.delay
        ).plan([self.task,urgent],self.dcs,self.now,self.manager,self.known)
        r=self.guard("guard0").review(
            [self.task,urgent],self.dcs,self.now,self.manager,self.known,plan
        )
        self.assertEqual(len(r["greedy_routes"]),2)
        self.assertIsInstance(r["accepted"],bool)

    def test_invalid_guard_mode_and_repeated_job_are_rejected(self):
        with self.assertRaises(ValueError):self.guard("unknown")
        with self.assertRaises(AssertionError):
            self.guard("guard0").review(
                [self.task,self.task],self.dcs,self.now,
                self.manager,self.known,
                {"routes":[1,1],"predictions":[None,None]}
            )

if __name__=="__main__":
    unittest.main()
