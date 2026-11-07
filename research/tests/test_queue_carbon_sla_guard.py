"""Deterministic checks for SLA-risk-preserving proxy-carbon selection."""
import unittest

from research.queue_aware_nsga2 import (
    carbon_sla_guard_choice, carbon_guard_choice,
    QueueAwareCarbonSlaGuard, QueueAwareFull,
)


class TestRiskSafeCarbonGuard(unittest.TestCase):
    def test_prevent_carbon_fallback_when_deadline_risk_worsens(self):
        scores={
            (1,1):(10,2,5),
            (2,2):(8,3,0),
        }
        score=lambda chrom:scores[tuple(chrom)]
        # Unrestricted guard would take the low-carbon but tardier reference.
        old, did=carbon_guard_choice((2,2),(1,1),score)
        self.assertTrue(did)
        self.assertEqual(old,[1,1])
        chosen, swapped, veto=carbon_sla_guard_choice((2,2),(1,1),score)
        self.assertFalse(swapped)
        self.assertTrue(veto)
        self.assertEqual(chosen,[2,2])

    def test_allow_carbon_fallback_when_predicted_tardiness_nonincreasing(self):
        scores={
            (1,1):(10,2,0),
            (2,2):(8,3,4),
        }
        chosen, swapped, veto=carbon_sla_guard_choice(
            (2,2),(1,1),lambda x:scores[tuple(x)]
        )
        self.assertEqual(chosen,[1,1])
        self.assertTrue(swapped)
        self.assertFalse(veto)

    def test_already_lower_carbon_keeps_optimized(self):
        scores={
            (1,1):(10,4,0),
            (2,2):(8,2,0),
        }
        chosen, swapped, veto=carbon_sla_guard_choice(
            (2,2),(1,1),lambda x:scores[tuple(x)]
        )
        self.assertEqual((chosen,swapped,veto),([2,2],False,False))

    def test_invalid_scores_rejected(self):
        with self.assertRaises(ValueError):
            carbon_sla_guard_choice((2,2),(1,1),lambda x:(1,2,float("nan")))

    def test_same_optimizer_budget_and_queue_features(self):
        new=QueueAwareCarbonSlaGuard(seed=137)
        old=QueueAwareFull(seed=137)
        self.assertEqual((new.population,new.generations),
                         (old.population,old.generations))
        self.assertTrue(new.sla_safe_guard)
        self.assertTrue(new.queue_aware)
        self.assertTrue(new.transfer_accounting)
        self.assertEqual(new.carbon_guard_vetoes,0)


if __name__=="__main__":
    unittest.main()
