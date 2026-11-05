"""Zero-simulator dependency tests for a causal, predecision gate."""
import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from research_sci.state_gate import FeasibleCoverageGate
from research_sci.test_queue_risk import IdentityTask,FakeDC


class GateTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.green=FakeDC(1,cores=4)
        self.red=FakeDC(2,cores=4)
        self.centers={"a":self.green,"b":self.red}
        self.manager=SimpleNamespace(
            get_dc_location=lambda origin:f"dc-{origin}",cloud_provider="aws"
        )
        self.gate=FeasibleCoverageGate(delay_fn=lambda *args:0)
        self.ok=IdentityTask("ok",duration=15,cpu=1,
                    deadline=self.now+timedelta(minutes=60))
        self.early=IdentityTask("impossible",duration=30,cpu=1,
                    deadline=self.now+timedelta(minutes=10))
        self.known={1:[],2:[]}

    def test_half_feasible_activates(self):
        d=self.gate.assess([self.ok,self.early],self.centers,self.now,
                            self.manager,self.known)
        self.assertEqual(d["feasible_tasks"],1)
        self.assertEqual(d["feasible_fraction"],0.5)
        self.assertTrue(d["activate"])

    def test_congestion_gate_off(self):
        busy=IdentityTask("busy",duration=100,cpu=4)
        busy.finish_time=self.now+timedelta(minutes=90)
        for dc in (self.green,self.red):
            dc.available_cores=0
            dc.running_tasks=[busy]
        d=self.gate.assess([self.ok,self.early],self.centers,self.now,
                           self.manager,self.known)
        self.assertEqual(d["feasible_tasks"],0)
        self.assertFalse(d["activate"])

    def test_single_job_does_not_trigger_beam(self):
        d=self.gate.assess([self.ok],self.centers,self.now,
                           self.manager,self.known)
        self.assertFalse(d["activate"])

    def test_completed_outcome_not_read_at_dispatch(self):
        self.ok.finish_time=self.now+timedelta(days=20)
        d=self.gate.assess([self.ok,self.early],self.centers,self.now,
                            self.manager,self.known)
        self.assertTrue(d["activate"])

    def test_gate_does_not_mutate_reservations(self):
        existing=IdentityTask("prior",duration=10,cpu=1)
        commits={1:[(self.now+timedelta(minutes=15),existing)],2:[]}
        original={k:list(v) for k,v in commits.items()}
        self.gate.assess([self.ok,self.early],self.centers,self.now,
                         self.manager,commits)
        self.assertEqual(commits,original)

    def test_bad_parameters(self):
        for bad in (0,1.1,-.2,float("nan")):
            with self.assertRaises(ValueError):
                FeasibleCoverageGate(threshold=bad,delay_fn=lambda *a:0)
        with self.assertRaises(ValueError):
            FeasibleCoverageGate(min_batch_size=1,delay_fn=lambda *a:0)

if __name__=="__main__":
    unittest.main()
