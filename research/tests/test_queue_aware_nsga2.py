"""Deterministic checks for FIFO queue projection and ablation isolation."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research.queue_aware_nsga2 import (
    predict_starts, QueueAwareFull, QueueAblationNoQueue,
    QueueAblationNoTransferCost,
)


def task(name, duration=10, cores=2):
    return SimpleNamespace(
        job_name=name, duration=duration, cores_req=cores, gpu_req=0,
        mem_req=0, bandwidth_gb=0, origin_dc_id=1,
    )


def dc(available=4, total=4, pending=(), running=()):
    return SimpleNamespace(
        available_cores=available, available_gpus=2, available_mem=100,
        total_cores=total, total_gpus=2, total_mem_GB=100,
        pending_tasks=list(pending), running_tasks=list(running),
    )


class TestQueuePredictor(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)

    def test_empty_queue_local_task_starts_now(self):
        t=task("A")
        self.assertEqual(predict_starts(dc(),[(t,self.now)],self.now)[t],self.now)

    def test_running_task_delays_new_task_until_release(self):
        executing=task("X",duration=30,cores=4)
        executing.finish_time=self.now+timedelta(minutes=30)
        newcomer=task("A",cores=4)
        predicted=predict_starts(dc(available=0,running=[executing]),[(newcomer,self.now)],self.now)
        self.assertEqual(predicted[newcomer],self.now+timedelta(minutes=30))

    def test_existing_pending_task_goes_first(self):
        earlier=task("P",duration=30,cores=4)
        later=task("A",duration=10,cores=4)
        result=predict_starts(dc(pending=[earlier]),[(later,self.now)],self.now)
        self.assertEqual(result[later],self.now+timedelta(minutes=30))

    def test_remote_task_is_not_available_early(self):
        a=task("remote")
        result=predict_starts(dc(),[(a,self.now+timedelta(minutes=15))],self.now)
        self.assertEqual(result[a],self.now+timedelta(minutes=15))

    def test_two_tasks_in_same_batch_contend(self):
        a=task("A",duration=30,cores=4)
        b=task("B",duration=10,cores=4)
        result=predict_starts(dc(),[(a,self.now),(b,self.now)],self.now)
        self.assertEqual(result[a],self.now)
        self.assertEqual(result[b],self.now+timedelta(minutes=30))

    def test_insufficient_physical_capacity_rejected(self):
        with self.assertRaises(ValueError):
            predict_starts(dc(total=1),[(task("big",cores=2),self.now)],self.now)


class TestAblationConfiguration(unittest.TestCase):
    def test_independent_flags_are_correct(self):
        p=QueueAwareFull()
        no_queue=QueueAblationNoQueue()
        no_transfer=QueueAblationNoTransferCost()
        self.assertEqual((p.queue_aware,p.transfer_accounting),(True,True))
        self.assertEqual((no_queue.queue_aware,no_queue.transfer_accounting),(False,True))
        self.assertEqual((no_transfer.queue_aware,no_transfer.transfer_accounting),(True,False))

    def test_all_ablations_share_optimizer_budget(self):
        for cls in (QueueAwareFull,QueueAblationNoQueue,QueueAblationNoTransferCost):
            policy=cls(seed=42,population=8,generations=4,delay_fn=lambda *a:0)
            self.assertEqual(policy.population,8)
            self.assertEqual(policy.generations,4)
            self.assertEqual(policy.surrogate_evaluations,0)


if __name__=="__main__":
    unittest.main()
