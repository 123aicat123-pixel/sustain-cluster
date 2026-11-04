"""Reproducible tests for the exact online NSGA-II algorithm and adaptor."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import random

from research.nsga2_core import (
    dominates, non_dominated_sort, crowding,
    environmental_selection, nsga2_optimize,
)
from research.nsga2_batch_policy import NSGA2BatchPolicy


class TestNSGA2Core(unittest.TestCase):
    def test_dominance_and_non_dominated_sort(self):
        self.assertTrue(dominates((1,2,3),(2,2,4)))
        self.assertFalse(dominates((1,2,3),(0,4,3)))
        scores=[(1,3,3),(3,1,3),(3,3,1),(4,4,4)]
        fronts=non_dominated_sort(scores)
        self.assertEqual(set(fronts[0]),{0,1,2})
        self.assertEqual(fronts[1],[3])

    def test_crowding_boundaries_and_elitism(self):
        scores=[(1,3,3),(2,2,2),(3,1,1),(4,4,4)]
        d=crowding([0,1,2],scores)
        self.assertEqual(d[0],float("inf"))
        self.assertEqual(d[2],float("inf"))
        surviving=environmental_selection(list(range(4)),scores,2)
        self.assertNotIn(3,surviving)

    def test_deterministic_and_feasible_with_evaluation_counts(self):
        choices=[[2,7],[2,7],[2,7]]
        def evaluate(g):
            return (sum(g), -sum(g), sum(x==7 for x in g))
        a=nsga2_optimize(choices,evaluate,rng=random.Random(24),population_size=8,generations=5)
        b=nsga2_optimize(choices,evaluate,rng=random.Random(24),population_size=8,generations=5)
        self.assertEqual(a,b)
        self.assertTrue(all(g in choices[i] for i,g in enumerate(a[0])))
        self.assertEqual(a[1]["evaluation_requests"],8*(1+3*5))
        self.assertLessEqual(a[1]["surrogate_evaluations"],2**3)
        self.assertGreaterEqual(a[1]["pareto_front_size"],1)

    def test_invalid_chromosome_rejected(self):
        with self.assertRaises(ValueError):
            nsga2_optimize([[2]],lambda x:(0,0,0),seeds=[[9]])


def dc(i, price, carbon, place):
    return SimpleNamespace(
        dc_id=i,location=place,available_cores=100,
        can_schedule=lambda t:True,
        get_current_carbon_intensity=lambda norm=False:carbon,
        price_manager=SimpleNamespace(get_current_price=lambda:price),
    )


class TestNSGA2Integration(unittest.TestCase):
    def test_actions_are_positions_not_numerical_dc_ids(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        tasks=[SimpleNamespace(
            origin_dc_id=7,bandwidth_gb=1,
            cores_req=1,duration=10,
            sla_deadline=start+timedelta(minutes=40)
        ) for _ in range(3)]
        dcs={"DC7":dc(7,100,100,"A"),"DC2":dc(2,110,200,"B")}
        cluster=SimpleNamespace(
            cloud_provider="aws",get_dc_location=lambda i:"A"
        )
        def go():
            p=NSGA2BatchPolicy(seed=4,population=8,generations=4,
                               delay_fn=lambda a,b,c,d:30)
            p.set_context(start,cluster)
            return p.select_batch(tasks,dcs),p.surrogate_evaluations,p.evaluation_requests
        a,b=go(),go()
        self.assertEqual(a,b)
        actions,fallback=a[0]
        self.assertEqual(len(actions),3)
        self.assertTrue(set(actions)<=set((1,2)))
        self.assertEqual(fallback,0)
        self.assertGreater(a[1],0)

    def test_no_tasks_has_no_optimizer_budget(self):
        p=NSGA2BatchPolicy(seed=2,delay_fn=lambda *args:0)
        self.assertEqual(p.select_batch([],{"DC2":dc(2,1,1,"A")}),([],0))
        self.assertEqual(p.surrogate_evaluations,0)


if __name__=="__main__":
    unittest.main()
