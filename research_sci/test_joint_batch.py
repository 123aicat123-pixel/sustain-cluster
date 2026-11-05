"""Predictor-consistent bounded joint matching, with no simulation libs."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from research_sci.joint_batch import JointBatchCarbonPlanner
from research_sci.test_queue_risk import FakeDC,IdentityTask
from research_sci.queue_risk import QueueRiskCarbonPolicy


class JointBatchTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.green=FakeDC(1,carbon=100,cores=1)
        self.red=FakeDC(2,carbon=500,cores=1)
        for dc in (self.green,self.red):
            dc.total_cores=1
        self.red.available_gpus=0
        self.red.total_gpus=1
        self.centers={"green":self.green,"red":self.red}
        self.manager=SimpleNamespace(
            get_dc_location=lambda dc_id:f"dc-{dc_id}",
            cloud_provider="aws"
        )
        self.delay=lambda *args:0
        self.flexible=IdentityTask("flex",duration=90,cpu=1,
                       deadline=self.now+timedelta(minutes=180))
        self.urgent=IdentityTask("urgent",duration=15,cpu=1,gpu=1,
                       deadline=self.now+timedelta(minutes=45))

    def planner(self,**kwargs):
        return JointBatchCarbonPlanner(delay_fn=self.delay,**kwargs)

    def test_lookahead_preserves_urgent_feasible_assignment(self):
        policy=QueueRiskCarbonPolicy("queue_risk_carbon",
                         delay_fn=self.delay,risk_buffer_minutes=30)
        greedy=policy.choose(self.flexible,self.centers,self.now,self.manager)
        self.assertEqual(greedy[0],1)
        result=self.planner(beam_width=4,chunk_size=8).plan(
            [self.flexible,self.urgent],self.centers,self.now,
            self.manager,{1:[],2:[]}
        )
        self.assertEqual(result["routes"],[2,1])
        self.assertLessEqual(result["predictions"][1],self.urgent.sla_deadline)
        self.assertEqual(result["chunks"],1)

    def test_seen_task_reservations_remain_unmodified(self):
        prior=IdentityTask("already-transit",duration=45,cpu=1)
        commits={1:[(self.now+timedelta(minutes=15),prior)],2:[]}
        snapshot={k:list(v) for k,v in commits.items()}
        result=self.planner().plan([self.flexible,self.urgent],self.centers,
                                   self.now,self.manager,commits)
        self.assertEqual(commits,snapshot)
        self.assertEqual(len(result["routes"]),2)

    def test_fixed_chunk_budget(self):
        many=[IdentityTask(f"t{i}",duration=15,cpu=1,
              deadline=self.now+timedelta(hours=4)) for i in range(5)]
        result=self.planner(chunk_size=2,beam_width=2).plan(
            many,self.centers,self.now,self.manager,{1:[],2:[]}
        )
        self.assertEqual(result["chunks"],3)
        self.assertEqual(len(result["routes"]),5)
        self.assertLessEqual(result["expansions"],5*2*2)

    def test_no_forecast_uses_original_origin_fallback(self):
        impossible=IdentityTask("large",duration=60,cpu=999,
                       deadline=self.now+timedelta(hours=4))
        impossible.origin_dc_id=2
        result=self.planner().plan([impossible],self.centers,self.now,
                                   self.manager,{1:[],2:[]})
        self.assertEqual(result["routes"],[2])
        self.assertIsNone(result["predictions"][0])

    def test_input_validation(self):
        for args in ({"beam_width":0},{"chunk_size":0},
                     {"risk_buffer_minutes":-1}):
            with self.assertRaises(ValueError): self.planner(**args)
        with self.assertRaises(AssertionError):
            self.planner().plan([self.flexible,self.flexible],self.centers,
                                self.now,self.manager,{1:[],2:[]})

if __name__=="__main__":
    unittest.main()
