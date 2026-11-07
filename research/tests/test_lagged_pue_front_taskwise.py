"""No added GA budget or PUE-reference leakage for cached front selector."""
import unittest
from types import SimpleNamespace
from research.queue_aware_nsga2 import (
    QueueAwareLaggedPUE, QueueAwareLaggedPUEFrontTaskwise
)
from research.transit_front_carbon import choose_front_carbon_under_taskwise_finish


def record(gene, carbon, finish):
    return {"chromosome": [gene], "surrogate": [1.0, carbon, 0.0]}


class PUEFrontTaskwiseTests(unittest.TestCase):
    def test_flag_and_initial_budget(self):
        candidate=QueueAwareLaggedPUE(seed=901)
        guarded=QueueAwareLaggedPUEFrontTaskwise(seed=901)
        self.assertEqual((candidate.population,candidate.generations),
                         (guarded.population,guarded.generations))
        self.assertFalse(getattr(candidate,"front_carbon_taskwise_enabled",False))
        self.assertTrue(guarded.front_carbon_taskwise_enabled)
        self.assertEqual(guarded.front_carbon_selection_checks,0)
        self.assertEqual(guarded.front_carbon_selection_changes,0)
        self.assertEqual(guarded.evaluation_requests,0)

    def test_lagged_pue_remains_action_conditional_only_on_past_observation(self):
        candidate=QueueAwareLaggedPUEFrontTaskwise(seed=901)
        self.assertEqual(candidate._facility_carbon_factor(1),1.0)
        candidate.observe_facility_after_step(
            {"dc":{"agent_dc":{"dc_ITE_total_power_kW":10.0,
                               "dc_HVAC_total_power_kW":5.0}}},
            {"dc":SimpleNamespace(dc_id=1)})
        self.assertEqual(candidate._facility_carbon_factor(1),1.5)
        candidate.reset()
        self.assertEqual(candidate._facility_carbon_factor(1),1.0)

    def test_taskwise_front_vetoes_later_completion(self):
        front=[record(1, 5.0, 30),record(2, 4.0, 45)]
        self.assertEqual(choose_front_carbon_under_taskwise_finish(
            [1],front,{(1,):(30.0,),(2,):(45.0,)}
        ),([1],False))

    def test_accepts_lower_proxy_carbon_and_nonlater_task_finish(self):
        front=[record(1, 5.0, 30),record(2, 4.0, 30)]
        self.assertEqual(choose_front_carbon_under_taskwise_finish(
            [1],front,{(1,):(30.0,),(2,):(30.0,)}
        ),([2],True))


if __name__=="__main__":
    unittest.main()
