"""Contract tests for lagged-PUE online shadow no-later completion guard."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research.lagged_pue_risk_policy import (
    QueueAwareLaggedPUEShadowGuard, choose_if_nonlater
)
from research.queue_aware_nsga2 import QueueAwareIndexedTransit


def item():
    return type("Task", (), {})()


class ShadowGateTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = item(), item()
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_revert_when_any_one_task_starts_later(self):
        shadow = {self.a: self.now, self.b: self.now}
        cand = {self.a: self.now,
                self.b: self.now + timedelta(minutes=15)}
        picked, reverted, late = choose_if_nonlater(
            [self.a, self.b], [1, 2], [2, 1], cand, shadow
        )
        self.assertEqual(picked, [2, 1])
        self.assertTrue(reverted)
        self.assertEqual(late, 1)

    def test_allow_nonlater_proposal(self):
        shadow = {self.a: self.now + timedelta(minutes=15), self.b: self.now}
        cand = {self.a: self.now, self.b: self.now}
        self.assertEqual(choose_if_nonlater(
            [self.a, self.b], [1, 2], [2, 1], cand, shadow
        ), ([1, 2], False, 0))

    def test_missing_task_rejected(self):
        with self.assertRaises(AssertionError):
            choose_if_nonlater([self.a], [1], [2], {}, {self.a: self.now})

    def test_independent_seed_and_full_optimizer_budget(self):
        guard = QueueAwareLaggedPUEShadowGuard(seed=901)
        plain = QueueAwareIndexedTransit(seed=901)
        self.assertEqual((guard.population, guard.generations),
                         (plain.population, plain.generations))
        self.assertEqual(guard._shadow.seed, 901)
        self.assertEqual(guard.shadow_evaluation_requests, 0)
        self.assertEqual(guard.risk_guard_reversions, 0)
        guard.observe_facility_after_step(
            {"dc": {"agent_dc": {
                "dc_ITE_total_power_kW": 10,
                "dc_HVAC_total_power_kW": 5
            }}},
            {"dc": SimpleNamespace(dc_id=3)},
        )
        self.assertEqual(guard._facility_carbon_factor(3), 1.5)
        self.assertEqual(guard._shadow._facility_carbon_factor(3), 1.0)
        guard.reset()
        self.assertEqual(guard._facility_carbon_factor(3), 1.0)
        self.assertEqual(guard.shadow_evaluation_requests, 0)


if __name__ == "__main__":
    unittest.main()
