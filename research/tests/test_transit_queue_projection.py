"""Transit-aware queue projection tests, with the original predictor unchanged."""
import unittest
from datetime import datetime,timedelta,timezone
from collections import deque
from types import SimpleNamespace

from research.queue_aware_nsga2 import (
    predict_starts,
    predict_starts_with_in_transit,
    QueueAwareWithTransit,
    QueueAwareFull,
)


def t(name, minutes=30, cores=4):
    obj=type("Task",(),{})()
    obj.job_name=name
    obj.cores_req=cores
    obj.gpu_req=0
    obj.mem_req=0
    obj.duration=minutes
    return obj


def dc():
    return SimpleNamespace(
        dc_id=7,available_cores=4,available_gpus=1,available_mem=100,
        total_cores=4,total_gpus=1,total_mem_GB=100,
        pending_tasks=deque(),running_tasks=[]
    )


class TestTransitAwareProjection(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)

    def test_already_in_transit_occupies_capacity_before_new_remote(self):
        old=t("earlier-transfer",minutes=30)
        new=t("new-transfer",minutes=10)
        ready=self.now+timedelta(minutes=15)
        naive=predict_starts(dc(),[(new,ready)],self.now)
        aware=predict_starts_with_in_transit(
            dc(),[(new,ready)],self.now,[(ready,old)]
        )
        self.assertEqual(naive[new],ready)
        self.assertEqual(aware[new],self.now+timedelta(minutes=45))
        self.assertEqual(set(aware),{new})

    def test_later_transit_does_not_delay_earlier_new_assignment(self):
        old=t("later-transfer")
        new=t("local-new",minutes=10)
        result=predict_starts_with_in_transit(
            dc(),[(new,self.now)],self.now,
            [(self.now+timedelta(minutes=15),old)]
        )
        self.assertEqual(result[new],self.now)

    def test_no_transit_is_identical_to_original(self):
        jobs=[t("a"),t("b")]
        incoming=[(jobs[0],self.now),(jobs[1],self.now)]
        self.assertEqual(
            predict_starts(dc(),incoming,self.now),
            predict_starts_with_in_transit(dc(),incoming,self.now,[])
        )

    def test_duplicate_task_rejected(self):
        item=t("same")
        with self.assertRaisesRegex(AssertionError,"duplicated"):
            predict_starts_with_in_transit(
                dc(),[(item,self.now)],self.now,[(self.now,item)]
            )

    def test_subclass_has_same_genetic_budget(self):
        new=QueueAwareWithTransit(seed=17)
        baseline=QueueAwareFull(seed=17)
        self.assertEqual((new.population,new.generations),
                         (baseline.population,baseline.generations))
        self.assertEqual((new.queue_aware,new.transfer_accounting),
                         (baseline.queue_aware,baseline.transfer_accounting))
        self.assertEqual(new._pending_transit_by_dc,{})

    def test_only_known_destination_names_accepted(self):
        p=QueueAwareWithTransit()
        with self.assertRaisesRegex(ValueError,"unknown"):
            p.set_in_transit([(self.now,t("old"),"bad-name")],
                             {"dc":dc()})


if __name__=="__main__":
    unittest.main()
