"""Taskwise predicted-completion carbon gate: independent contract tests."""
import random
import unittest

from research.transit_front_carbon import choose_front_carbon_under_taskwise_finish
from research.nsga2_core import nsga2_optimize
from research.queue_aware_nsga2 import QueueAwareWithTransit, QueueAwareFrontCarbonTaskwise


def record(chrom, carbon, tardiness=0, cost=10):
    return {"chromosome": list(chrom), "surrogate": [cost, carbon, tardiness]}


class TestFrontCarbonTaskwise(unittest.TestCase):
    def test_rejects_future_risk_shift_between_tasks(self):
        # Same total tardiness / missed count could hide a task being delayed.
        front = [record((1,1),10,10), record((2,2),8,10)]
        predicted = {(1,1):(60.0,90.0), (2,2):(90.0,60.0)}
        result = choose_front_carbon_under_taskwise_finish([1,1],front,predicted)
        self.assertEqual(result,([1,1],False))

    def test_accepts_only_per_task_nonlater_completion(self):
        front = [record((1,1),10,5), record((2,2),8,4)]
        predicted = {(1,1):(60.0,90.0), (2,2):(60.0,75.0)}
        self.assertEqual(
            choose_front_carbon_under_taskwise_finish([1,1],front,predicted),
            ([2,2],True))

    def test_rejects_higher_carbon_even_if_faster(self):
        front = [record((1,),10,1), record((2,),12,0)]
        self.assertEqual(choose_front_carbon_under_taskwise_finish(
            [1],front,{(1,):(45,),(2,):(30,)}),([1],False))

    def test_missing_or_misaligned_prediction_rejected(self):
        front=[record((1,),10),record((2,),8)]
        with self.assertRaises(ValueError):
            choose_front_carbon_under_taskwise_finish([1],front,{(1,):(30,)})
        with self.assertRaises(ValueError):
            choose_front_carbon_under_taskwise_finish(
                [1],front,{(1,):(30,),(2,):(30,45)})

    def test_genetic_budget_same_as_full_transit(self):
        a=QueueAwareFrontCarbonTaskwise(seed=2026)
        b=QueueAwareWithTransit(seed=2026)
        self.assertEqual((a.population,a.generations),
                         (b.population,b.generations))
        self.assertEqual(a.front_carbon_selection_checks,0)
        def fitness(chrom):
            return float(chrom[0]),float(3-chrom[0]),0.0
        _, m=nsga2_optimize([[1,2]],fitness,rng=random.Random(3))
        self.assertEqual(m["evaluation_requests"],400)


if __name__=="__main__":
    unittest.main()
