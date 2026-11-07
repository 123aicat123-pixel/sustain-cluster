"""Ablation tests: explicit proxy-carbon guard, never actual-emission guarantee."""
import unittest

from research.queue_aware_nsga2 import (
    carbon_guard_choice, QueueAwareCarbonGuard, QueueAwareFull,
)


def proxy(chrom):
    if tuple(chrom)==(1,1):
        return (10, 2, 0)
    if tuple(chrom)==(2,2):
        return (8, 3, 0)
    return (9, 2, 1)


class TestProxyCarbonGuard(unittest.TestCase):
    def test_over_budget_falls_back_to_reference(self):
        result, changed=carbon_guard_choice((2,2),(1,1),proxy)
        self.assertTrue(changed)
        self.assertEqual(result,[1,1])

    def test_within_budget_retains_optimized(self):
        result, changed=carbon_guard_choice((1,2),(1,1),proxy)
        self.assertFalse(changed)
        self.assertEqual(result,[1,2])

    def test_margin_allows_small_overrun(self):
        result, changed=carbon_guard_choice((2,2),(1,1),proxy,margin=.5)
        self.assertFalse(changed)
        self.assertEqual(result,[2,2])

    def test_margin_validation(self):
        with self.assertRaises(ValueError):
            carbon_guard_choice((2,2),(1,1),proxy,margin=-0.001)

    def test_nonfinite_proxy_rejected(self):
        with self.assertRaises(ValueError):
            carbon_guard_choice((2,2),(1,1),lambda x:(0,float('nan'),0))

    def test_guard_only_changes_post_selection(self):
        guard=QueueAwareCarbonGuard(seed=4)
        normal=QueueAwareFull(seed=4)
        self.assertEqual(guard.population,normal.population)
        self.assertEqual(guard.generations,normal.generations)
        self.assertEqual(guard.queue_aware,normal.queue_aware)
        self.assertEqual(guard.transfer_accounting,normal.transfer_accounting)
        self.assertEqual(guard.carbon_guard_checks,0)
        self.assertEqual(guard.carbon_guard_interventions,0)


if __name__=="__main__":
    unittest.main()
