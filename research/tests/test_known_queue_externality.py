"""Falsification tests for known-queue counterfactual externality probe."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research.known_queue_externality import (
    known_queue_externality, project_tracked_starts
)
from research.queue_aware_nsga2 import predict_starts_with_in_transit


def task(name, minutes=30):
    obj=type("Task",(),{})()
    obj.job_name=name
    obj.cores_req=1
    obj.gpu_req=0
    obj.mem_req=0
    obj.duration=minutes
    obj.sla_deadline=datetime(2026,1,1,0,50,tzinfo=timezone.utc)
    return obj


def dc(pending=(), running=(), available=1):
    return SimpleNamespace(
        total_cores=1, total_gpus=0, total_mem_GB=0,
        available_cores=available, available_gpus=0, available_mem=0,
        pending_tasks=list(pending), running_tasks=list(running),
    )


class KnownQueueExternalityTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)

    def test_committed_transit_later_harmed_by_new_placement(self):
        committed=task("transit",15)
        incoming=task("new",45)
        result=known_queue_externality(
            dc(), [(incoming,self.now)], self.now,
            [(self.now+timedelta(minutes=15),committed)]
        )
        self.assertEqual(result["known_committed_tasks"],1)
        self.assertEqual(result["known_tasks_delayed"],1)
        self.assertEqual(result["known_added_wait_minutes"],30.0)
        self.assertEqual(result["known_added_tardiness_minutes"],10.0)

    def test_no_added_action_has_no_externality(self):
        queued=task("pending")
        result=known_queue_externality(dc(pending=[queued]), [], self.now)
        self.assertEqual(result["known_tasks_delayed"],0)
        self.assertEqual(result["known_added_tardiness_minutes"],0.0)

    def test_prediction_matches_existing_fifo_on_new_arrivals(self):
        incoming=task("new",15)
        committed=task("transit",15)
        future=self.now+timedelta(minutes=15)
        expected=predict_starts_with_in_transit(
            dc(),[(incoming,self.now)],self.now,[(future,committed)],
            indexed_membership=True)
        actual=project_tracked_starts(
            dc(),[(committed,future),(incoming,self.now)],self.now)
        self.assertEqual(expected[incoming],actual[incoming])

    def test_duplicate_identity_rejected(self):
        item=task("repeat")
        with self.assertRaises(AssertionError):
            known_queue_externality(
                dc(pending=[item]),[(item,self.now)],self.now)

    def test_invalid_capacity_rejected(self):
        incoming=task("huge")
        incoming.cores_req=2
        with self.assertRaises(ValueError):
            known_queue_externality(dc(),[(incoming,self.now)],self.now)

    def test_later_queue_timestamps_no_future_admissions(self):
        in_transit=task("future",15)
        result=known_queue_externality(
            dc(),[],self.now,
            [(self.now+timedelta(minutes=30),in_transit)])
        self.assertEqual(result["known_committed_tasks"],1)
        self.assertEqual(result["known_added_wait_minutes"],0.0)


if __name__=="__main__":
    unittest.main()
