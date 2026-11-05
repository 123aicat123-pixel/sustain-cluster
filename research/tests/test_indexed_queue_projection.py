"""Indexed queue-membership ablation must preserve FIFO timing and errors."""
import random
import unittest
from collections import deque
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research.queue_aware_nsga2 import (
    QueueAwareIndexedTransit, QueueAwareWithTransit, predict_starts,
    predict_starts_with_in_transit,
)


def task(name, cores=1, duration=30):
    return SimpleNamespace(job_name=name, cores_req=cores, gpu_req=0,
                           mem_req=0, duration=duration)


def center(cores):
    return SimpleNamespace(
        dc_id=1, total_cores=cores, available_cores=cores,
        total_gpus=1, available_gpus=1,
        total_mem_GB=100, available_mem=100,
        running_tasks=[], pending_tasks=deque(),
    )


class IndexedProjectionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_same_budget_and_initial_state(self):
        a, b = QueueAwareWithTransit(seed=123), QueueAwareIndexedTransit(seed=123)
        self.assertEqual((a.population, a.generations),
                         (b.population, b.generations))
        self.assertFalse(a.indexed_membership)
        self.assertTrue(b.indexed_membership)

    def test_randomized_fifo_and_in_transit_equal(self):
        rng = random.Random(8123)
        for case in range(150):
            cores = rng.choice((2, 4, 8))
            incoming = [(task(f"new-{case}-{i}", rng.randint(1, cores),
                              rng.choice((15, 30, 45))),
                         self.now + timedelta(minutes=15 * rng.randrange(3)))
                        for i in range(rng.randint(1, 4))]
            transit = [(self.now + timedelta(minutes=15 * rng.randrange(3)),
                        task(f"old-{case}-{i}", rng.randint(1, cores),
                             rng.choice((15, 30, 45))))
                       for i in range(rng.randrange(4))]
            legacy = predict_starts_with_in_transit(
                center(cores), incoming, self.now, transit)
            indexed = predict_starts_with_in_transit(
                center(cores), incoming, self.now, transit,
                indexed_membership=True)
            self.assertEqual(legacy, indexed, f"case {case}")
            self.assertEqual(
                predict_starts(center(cores), incoming, self.now),
                predict_starts(center(cores), incoming, self.now,
                               indexed_membership=True),
            )

    def test_duplicate_and_capacity_failure_unchanged(self):
        one = task("dup")
        for indexed in (False, True):
            with self.subTest(indexed=indexed):
                with self.assertRaisesRegex(AssertionError, "duplicated"):
                    predict_starts_with_in_transit(
                        center(2), [(one, self.now)], self.now,
                        [(self.now, one)], indexed_membership=indexed)
                with self.assertRaisesRegex(ValueError, "exceeds"):
                    predict_starts(center(2), [(task("large", cores=3), self.now)],
                                   self.now, indexed_membership=indexed)


if __name__ == "__main__":
    unittest.main()
