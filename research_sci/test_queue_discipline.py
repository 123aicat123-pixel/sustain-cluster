"""Standalone EDF tests: matching queue predictor and real deque execution."""
from collections import deque
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from research_sci.queue_discipline import (
    priority_key, sort_pending_queue, install_queue_discipline,
)
from research_sci.queue_risk import predict_finish, QueueRiskCarbonPolicy
from research_sci.test_queue_risk import IdentityTask, FakeDC


class EDFQueueTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_edf_beats_fifo_on_urgent_target_while_waiting(self):
        dc = FakeDC(1, cores=0)
        runner = IdentityTask("running", duration=30, cpu=2)
        runner.finish_time = self.now + timedelta(minutes=30)
        dc.running_tasks = [runner]
        dc.pending_tasks = deque([
            IdentityTask("slow",duration=90,cpu=2,
                         deadline=self.now+timedelta(hours=8))
        ])
        target=IdentityTask("urgent",duration=15,cpu=2,
                            deadline=self.now+timedelta(minutes=65))
        fifo=predict_finish(target,dc,self.now,1,queue_order="fifo")
        edf=predict_finish(target,dc,self.now,1,queue_order="edf")
        self.assertEqual(fifo,self.now+timedelta(minutes=135))
        self.assertEqual(edf,self.now+timedelta(minutes=45))
        self.assertLess(edf, target.sla_deadline)

    def test_actual_step_wrapper_sorts_new_arrivals_before_processing(self):
        dc=SimpleNamespace(pending_tasks=deque(),seen=[])
        def original_step(action_dict, logger):
            dc.seen=list(dc.pending_tasks)
            return "ok"
        dc.step=original_step
        install_queue_discipline({"dc":dc},"edf")
        later=IdentityTask("later",deadline=self.now+timedelta(hours=3))
        earlier=IdentityTask("earlier",deadline=self.now+timedelta(hours=1))
        dc.pending_tasks.extend([later,earlier])
        self.assertEqual(dc.step({},None),"ok")
        self.assertEqual([x.job_name for x in dc.seen],["earlier","later"])
        with self.assertRaises(AssertionError):
            install_queue_discipline({"dc":dc},"edf")

    def test_fifo_does_not_wrap_or_reorder(self):
        dc=SimpleNamespace(pending_tasks=deque([2,1]),step=lambda a,l:"ok")
        install_queue_discipline({"dc":dc},"fifo")
        self.assertEqual(list(dc.pending_tasks),[2,1])
        self.assertEqual(dc.step({},None),"ok")

    def test_equal_deadlines_are_deterministic(self):
        deadline=self.now+timedelta(hours=1)
        x=IdentityTask("x",duration=40,deadline=deadline)
        y=IdentityTask("y",duration=15,deadline=deadline)
        self.assertEqual(sorted([x,y],key=priority_key),[y,x])

    def test_edf_predictions_do_not_mutate_real_pending_queue(self):
        dc=FakeDC(1, cores=2)
        dc.pending_tasks=deque([
            IdentityTask("later",deadline=self.now+timedelta(hours=5))
        ])
        task=IdentityTask("now",deadline=self.now+timedelta(hours=1))
        initial=list(dc.pending_tasks)
        predict_finish(task,dc,self.now,1,queue_order="edf")
        self.assertEqual(list(dc.pending_tasks),initial)

    def test_bad_order_and_missing_deadline_fail(self):
        t=IdentityTask("missing")
        with self.assertRaises(ValueError):
            priority_key(t)
        with self.assertRaises(ValueError):
            predict_finish(t,FakeDC(1),self.now,1,queue_order="invalid")
        with self.assertRaises(ValueError):
            QueueRiskCarbonPolicy("queue_risk_carbon",queue_order="invalid")

if __name__=="__main__":
    unittest.main()
