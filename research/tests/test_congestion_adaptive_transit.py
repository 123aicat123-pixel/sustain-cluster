"""Fixed-budget capacity/relevance gate ablation contracts."""
import unittest
import random
from collections import deque
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research.queue_aware_nsga2 import (
    relevant_transit_competition, transit_may_compete_fast, predict_starts,
    predict_starts_with_in_transit, QueueAwareCongestionAdaptive,
    QueueAwareWithTransit
)


def task(name, cores=4, minutes=30):
    t=type("Task", (), {})()
    t.job_name=name
    t.cores_req=cores
    t.gpu_req=0
    t.mem_req=0
    t.duration=minutes
    return t


def dc(cores=4):
    return SimpleNamespace(
        dc_id=1, total_cores=cores, available_cores=cores,
        total_gpus=1, available_gpus=1,
        total_mem_GB=100, available_mem=100,
        pending_tasks=deque(), running_tasks=[]
    )


class TestAdaptiveTransit(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)

    def test_no_transit_skips_full_projection(self):
        d=dc()
        new=task("new")
        arrivals=[(new,self.now)]
        relevant,starts=relevant_transit_competition(d,arrivals,self.now,[])
        self.assertFalse(relevant)
        self.assertEqual(starts,predict_starts(d,arrivals,self.now))

    def test_late_transit_ignored(self):
        d=dc()
        new=task("new")
        arrivals=[(new,self.now)]
        transit=[(self.now+timedelta(minutes=15),task("old"))]
        relevant,starts=relevant_transit_competition(d,arrivals,self.now,transit)
        self.assertFalse(relevant)
        self.assertEqual(starts[new],self.now)

    def test_competing_transit_changes_prediction(self):
        d=dc()
        new=task("new")
        old=task("transit")
        ready=self.now+timedelta(minutes=15)
        arrivals=[(new,ready)]
        transit=[(ready,old)]
        relevant,base=relevant_transit_competition(d,arrivals,self.now,transit)
        self.assertTrue(relevant)
        self.assertEqual(base[new],ready)
        policy=QueueAwareCongestionAdaptive(seed=1)
        policy._pending_transit_by_dc={1:transit}
        actual=policy._project_starts(d,arrivals,self.now)
        self.assertEqual(actual[new],self.now+timedelta(minutes=45))
        self.assertEqual(policy.adaptive_projection_checks,1)
        self.assertEqual(policy.adaptive_transit_projections,1)

    def test_sufficient_capacity_allows_shortcut(self):
        d=dc(cores=12)
        new=task("new",cores=4)
        old=task("transit",cores=4)
        ready=self.now+timedelta(minutes=15)
        arrivals=[(new,ready)]
        transit=[(ready,old)]
        relevant,base=relevant_transit_competition(d,arrivals,self.now,transit)
        self.assertFalse(relevant)
        full=predict_starts_with_in_transit(d,arrivals,self.now,transit)
        self.assertEqual(full,base)

    def test_fast_gate_skips_noninterfering_transfer(self):
        d=dc(cores=4)
        new=task("new",cores=4)
        old=task("transit",cores=4)
        arrivals=[(new,self.now)]
        transfer=[(self.now+timedelta(minutes=15),old)]
        self.assertFalse(transit_may_compete_fast(d,arrivals,self.now,transfer))
        p=QueueAwareCongestionAdaptive()
        p._pending_transit_by_dc={1:transfer}
        self.assertEqual(p._project_starts(d,arrivals,self.now)[new],self.now)
        self.assertEqual(p.adaptive_transit_projections,0)
        self.assertEqual(p.adaptive_base_projections,1)

    def test_fast_gate_matches_full_projection_on_seeded_small_cases(self):
        rng=random.Random(1901)
        for case in range(100):
            d=dc(cores=rng.choice([4,8,12]))
            ready=[self.now+timedelta(minutes=15*rng.randrange(4))
                   for _ in range(3)]
            incoming=[(task(f"new-{case}-{j}",cores=rng.choice([1,2,4]),
                            minutes=rng.choice([15,30,45])),ready[j])
                      for j in range(rng.choice([1,2,3]))]
            transfer=[(self.now+timedelta(minutes=15*rng.randrange(4)),
                       task(f"transfer-{case}-{j}",
                            cores=rng.choice([1,2,4]),minutes=rng.choice([15,30,45])))
                      for j in range(rng.randrange(3))]
            gate=transit_may_compete_fast(d,incoming,self.now,transfer)
            base=predict_starts(d,incoming,self.now)
            full=predict_starts_with_in_transit(d,incoming,self.now,transfer)
            if not gate:
                self.assertEqual(base,full,f"unsafe shortcut case {case}")

    def test_same_genetic_budget_and_reset_counters(self):
        base=QueueAwareWithTransit(seed=23)
        adapt=QueueAwareCongestionAdaptive(seed=23)
        self.assertEqual((base.population,base.generations),
                         (adapt.population,adapt.generations))
        self.assertEqual((base.queue_aware,base.transfer_accounting),
                         (adapt.queue_aware,adapt.transfer_accounting))
        adapt.adaptive_projection_checks=17
        adapt.reset()
        self.assertEqual(adapt.adaptive_projection_checks,0)
        self.assertEqual(adapt.adaptive_transit_projections,0)
        self.assertEqual(adapt.adaptive_base_projections,0)


if __name__ == "__main__":
    unittest.main()
