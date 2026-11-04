"""Deterministic, dataset-free contract tests for SCI pilot schedulers."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research_sci.policies import SpatialPolicy


class FakeDC:
    def __init__(self, dc_id, carbon, available=True):
        self.dc_id = dc_id
        self.location = f"loc-{dc_id}"
        self.carbon = carbon
        self.available = available

    def can_schedule(self, task):
        return self.available

    def get_current_carbon_intensity(self, norm=False):
        return self.carbon


class SpatialPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.cluster = SimpleNamespace(
            cloud_provider="aws", get_dc_location=lambda i: "origin"
        )
        self.centers = {"A": FakeDC(1, 500), "B": FakeDC(2, 100)}
        self.task = SimpleNamespace(
            origin_dc_id=1,
            bandwidth_gb=1,
            duration=30,
            sla_deadline=self.now + timedelta(minutes=60),
        )
        self.delay = lambda src, dst, provider, data: 0 if dst == "loc-1" else 3600

    def policy(self, name):
        return SpatialPolicy(name, delay_fn=self.delay)

    def test_lowest_carbon_ignores_deadline(self):
        self.assertEqual(self.policy("lowest_carbon").choose(
            self.task, self.centers, self.now, self.cluster), (2, False))

    def test_deadline_feasible_carbon_chooses_on_time_center(self):
        self.assertEqual(self.policy("sla_carbon").choose(
            self.task, self.centers, self.now, self.cluster), (1, False))

    def test_deadline_infeasible_falls_back_to_fastest(self):
        self.task.sla_deadline = self.now + timedelta(minutes=5)
        self.assertEqual(self.policy("sla_carbon").choose(
            self.task, self.centers, self.now, self.cluster), (1, False))

    def test_fastest_finish(self):
        self.assertEqual(self.policy("fastest_finish").choose(
            self.task, self.centers, self.now, self.cluster), (1, False))

    def test_capacity_mask_common_to_all_policies(self):
        self.centers["A"].available = False
        for name in SpatialPolicy.NAMES:
            with self.subTest(name=name):
                self.assertEqual(self.policy(name).choose(
                    self.task, self.centers, self.now, self.cluster), (2, False))

    def test_no_capacity_is_explicit_fallback(self):
        for dc in self.centers.values():
            dc.available = False
        for name in SpatialPolicy.NAMES:
            with self.subTest(name=name):
                self.assertEqual(self.policy(name).choose(
                    self.task, self.centers, self.now, self.cluster), (1, True))

    def test_round_robin_deterministic(self):
        policy = self.policy("round_robin")
        picks = [policy.choose(self.task, self.centers, self.now, self.cluster)[0]
                 for _ in range(5)]
        self.assertEqual(picks, [1, 2, 1, 2, 1])

    def test_invalid_network_delay_fails_loudly(self):
        policy = SpatialPolicy("sla_carbon", delay_fn=lambda *args: -1)
        with self.assertRaises(ValueError):
            policy.choose(self.task, self.centers, self.now, self.cluster)


if __name__ == "__main__":
    unittest.main()
