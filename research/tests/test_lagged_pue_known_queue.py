"""Known-queue one-search policy and within-decision memoization contracts."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research.known_queue_externality import (
    known_queue_externality, project_tracked_starts
)
from research.queue_aware_nsga2 import (
    QueueAwareLaggedPUEKnownQueue, QueueAwareLaggedPUE
)


def task(name, duration=30, deadline=50):
    item=type("Task", (), {})()
    item.job_name=name
    item.cores_req=1
    item.gpu_req=0
    item.mem_req=0
    item.duration=duration
    item.sla_deadline=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=deadline)
    return item


def dc(pending=()):
    return SimpleNamespace(
        dc_id=1, total_cores=1, total_gpus=0, total_mem_GB=0,
        available_cores=1, available_gpus=0, available_mem=0,
        pending_tasks=list(pending), running_tasks=[]
    )


class KnownQueueFitnessTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)

    def test_one_search_configuration_is_identical(self):
        original=QueueAwareLaggedPUE(seed=901)
        treatment=QueueAwareLaggedPUEKnownQueue(seed=901)
        self.assertEqual(
            (original.population, original.generations),
            (treatment.population, treatment.generations))
        self.assertTrue(treatment.known_queue_externality_enabled)
        self.assertFalse(getattr(original,"known_queue_externality_enabled",False))
        self.assertEqual(treatment.evaluation_requests,0)
        self.assertEqual(treatment.known_queue_extra_calls,0)

    def test_objective_changes_for_committed_future_transit(self):
        new=task("new",duration=45)
        committed=task("transit",duration=15)
        site=dc()
        policy=QueueAwareLaggedPUEKnownQueue(seed=901)
        policy._pending_transit_by_dc={1:[
            (self.now+timedelta(minutes=15),committed)
        ]}
        arrangements={1:[(new,self.now)]}
        penalty=policy._known_queue_penalty([site],arrangements,self.now)
        self.assertEqual(penalty,10)
        self.assertEqual(policy.known_queue_extra_calls,1)
        self.assertEqual(policy.known_queue_baseline_calls,1)
        # Same decision: reuse the no-dispatch projection instead of recomputing.
        self.assertEqual(policy._known_queue_penalty([site],arrangements,self.now),10)
        self.assertEqual(policy.known_queue_extra_calls,2)
        self.assertEqual(policy.known_queue_baseline_calls,1)
        self.assertEqual(policy.known_queue_positive_penalty_calls,2)

    def test_existing_baseline_unchanged_by_cache(self):
        committed=task("transfer",duration=15)
        incoming=task("incoming",duration=45)
        site=dc()
        transit=[(self.now+timedelta(minutes=15),committed)]
        baseline=project_tracked_starts(
            site,[(committed,transit[0][0])],self.now)
        raw=known_queue_externality(
            site,[(incoming,self.now)],self.now,transit)
        cached=known_queue_externality(
            site,[(incoming,self.now)],self.now,transit,
            baseline_starts=baseline)
        self.assertEqual(cached,raw)

    def test_stale_baseline_rejected(self):
        site=dc()
        existing=task("existing")
        with self.assertRaises(AssertionError):
            known_queue_externality(
                site,[],self.now,[(self.now,existing)],
                baseline_starts={}
            )

    def test_reset_clears_counters(self):
        policy=QueueAwareLaggedPUEKnownQueue(seed=901)
        policy.known_queue_extra_calls=8
        policy.known_queue_selected_penalty_minutes=27
        policy.known_queue_selected_positive_batches=3
        policy.known_queue_selected_decisions=4
        policy._known_queue_reference={1:{"bad":3}}
        policy._known_queue_candidate_penalties={(1,):27}
        policy.reset()
        self.assertEqual(policy.known_queue_extra_calls,0)
        self.assertEqual(policy.known_queue_selected_penalty_minutes,0)
        self.assertEqual(policy.known_queue_selected_positive_batches,0)
        self.assertEqual(policy.known_queue_selected_decisions,0)
        self.assertEqual(policy._known_queue_reference,{})
        self.assertEqual(policy._known_queue_candidate_penalties,{})


if __name__=="__main__":
    unittest.main()
