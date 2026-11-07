"""Post-search carbon compromise requires two non-increasing SLA proxies."""
import unittest
import random
from research.transit_front_carbon import choose_front_carbon_under_risk
from research.nsga2_core import nsga2_optimize
from research.queue_aware_nsga2 import QueueAwareFrontCarbonRisk, QueueAwareWithTransit


def rec(chrom, cost, carbon, tardy):
    return {"chromosome":list(chrom),"surrogate":[cost,carbon,tardy]}


class TestFrontCarbonRisk(unittest.TestCase):
    def test_rejects_better_carbon_when_deadline_count_worsens(self):
        candidates=[rec((1,),10,10,5),rec((2,),11,8,4)]
        got,changed=choose_front_carbon_under_risk(
            [1],candidates,{(1,):1,(2,):2})
        self.assertEqual(got,[1])
        self.assertFalse(changed)

    def test_rejects_better_carbon_when_total_tardiness_worsens(self):
        candidates=[rec((1,),10,10,5),rec((2,),11,8,8)]
        got,changed=choose_front_carbon_under_risk(
            [1],candidates,{(1,):1,(2,):1})
        self.assertEqual((got,changed),([1],False))

    def test_selects_strictly_lower_carbon_with_same_risk(self):
        candidates=[rec((1,),10,10,5),rec((2,),15,8,5)]
        got,changed=choose_front_carbon_under_risk(
            [1],candidates,{(1,):1,(2,):1})
        self.assertEqual((got,changed),([2],True))

    def test_invalid_missing_risk_rejected(self):
        with self.assertRaises(ValueError):
            choose_front_carbon_under_risk(
                [1],[rec((1,),10,10,5)],{})

    def test_final_front_is_already_evaluated_no_added_budget(self):
        def f(chrom):
            x=chrom[0]
            return x, 3-x, 1
        _,m=nsga2_optimize([[1,2]],f,rng=random.Random(42))
        self.assertTrue(m["final_front_records"])
        self.assertTrue(all(len(x["surrogate"])==3
                            for x in m["final_front_records"]))
        self.assertEqual(m["evaluation_requests"],400)
        self.assertEqual(m["surrogate_evaluations"],2)

    def test_same_search_budget_as_full_transit(self):
        a=QueueAwareFrontCarbonRisk(seed=19)
        b=QueueAwareWithTransit(seed=19)
        self.assertEqual((a.population,a.generations),(b.population,b.generations))
        self.assertTrue(a.front_carbon_risk_enabled)
        self.assertEqual(a.front_carbon_selection_checks,0)
        self.assertEqual(a.front_carbon_selection_changes,0)


if __name__=="__main__":
    unittest.main()
