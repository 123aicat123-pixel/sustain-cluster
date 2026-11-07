"""Deterministic contract tests for SustainCluster's original rule-based schedulers.

These are lightweight selector-level checks. They intentionally do NOT claim to
validate the full simulator, physical models, task trace, or experiment results.
Run with: python -m unittest discover -s research/tests -p 'test_*.py' -v
"""
import unittest
from types import SimpleNamespace

from utils.task_assignment_strategies import (
    DistributeRoundRobin,
    DistributeMostAvailable,
    DistributeLeastPending,
    DistributeLowestPrice,
    DistributeLowestCarbon,
    DistributeLocalOnly,
)


class DummyDC:
    def __init__(self, dc_id, *, price=100.0, carbon=400.0,
                 cores=100, pending=0, feasible=True):
        self.dc_id = dc_id
        self.available_cores = cores
        self.pending_tasks = [object() for _ in range(pending)]
        self.feasible = feasible
        self.price_manager = SimpleNamespace(get_current_price=lambda: price)
        self._carbon = carbon

    def can_schedule(self, task):
        return self.feasible

    def get_current_carbon_intensity(self, norm=False):
        return self._carbon


TASK = SimpleNamespace(job_name="contract-task", origin_dc_id=2)


class TestRuleBasedBaselineContracts(unittest.TestCase):
    def setUp(self):
        self.dcs = {
            "DC1": DummyDC(1, price=90, carbon=700, cores=15, pending=5),
            "DC2": DummyDC(2, price=130, carbon=150, cores=80, pending=1),
            "DC3": DummyDC(3, price=110, carbon=300, cores=30, pending=3),
        }

    def test_lowest_price(self):
        self.assertEqual(DistributeLowestPrice()(TASK, self.dcs), 1)

    def test_lowest_carbon(self):
        self.assertEqual(DistributeLowestCarbon()(TASK, self.dcs), 2)

    def test_most_available(self):
        self.assertEqual(DistributeMostAvailable()(TASK, self.dcs), 2)

    def test_least_pending(self):
        self.assertEqual(DistributeLeastPending()(TASK, self.dcs), 2)

    def test_local_only(self):
        self.assertEqual(DistributeLocalOnly()(TASK, self.dcs), 2)

    def test_round_robin_wrap_and_reset(self):
        policy = DistributeRoundRobin()
        actual = [policy(TASK, self.dcs) for _ in range(4)]
        self.assertEqual(actual, [1, 2, 3, 1])
        policy.reset()
        self.assertEqual(policy(TASK, self.dcs), 1)

    def test_price_filters_infeasible_center(self):
        self.dcs["DC1"].feasible = False
        self.assertEqual(DistributeLowestPrice()(TASK, self.dcs), 3)

    def test_carbon_filters_infeasible_center(self):
        self.dcs["DC2"].feasible = False
        self.assertEqual(DistributeLowestCarbon()(TASK, self.dcs), 3)

    def test_most_available_filters_infeasible_center(self):
        self.dcs["DC2"].feasible = False
        self.assertEqual(DistributeMostAvailable()(TASK, self.dcs), 3)

    def test_no_feasible_dc_returns_none_for_price_carbon_capacity(self):
        for dc in self.dcs.values():
            dc.feasible = False
        for strategy in (DistributeLowestPrice(), DistributeLowestCarbon(),
                         DistributeMostAvailable()):
            with self.subTest(strategy=type(strategy).__name__):
                self.assertIsNone(strategy(TASK, self.dcs))

    def test_no_datacenters(self):
        for strategy in (DistributeRoundRobin(), DistributeLeastPending(),
                         DistributeLowestPrice(), DistributeLowestCarbon(),
                         DistributeMostAvailable()):
            with self.subTest(strategy=type(strategy).__name__):
                self.assertIsNone(strategy(TASK, {}))

    def test_least_pending_current_behavior_does_not_filter_capacity(self):
        """Documents a fairness risk in the ORIGINAL implementation; not a fix."""
        self.dcs["DC2"].feasible = False
        self.assertEqual(DistributeLeastPending()(TASK, self.dcs), 2)

    def test_round_robin_current_behavior_does_not_filter_capacity(self):
        """RoundRobin can select a non-schedulable DC; document before comparison."""
        self.dcs["DC1"].feasible = False
        self.assertEqual(DistributeRoundRobin()(TASK, self.dcs), 1)


if __name__ == "__main__":
    unittest.main()
