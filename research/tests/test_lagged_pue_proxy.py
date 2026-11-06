"""Lagged site-PUE proxy contracts: no leakage, reset and fallback."""
import unittest
from types import SimpleNamespace

from research.lagged_pue_proxy import (
    observed_pue, observed_facility_multipliers
)
from research.queue_aware_nsga2 import QueueAwareLaggedPUE, QueueAwareIndexedTransit


def sample(it, hvac):
    return {"agent_dc": {
        "dc_ITE_total_power_kW": it,
        "dc_HVAC_total_power_kW": hvac,
    }}


class LaggedFacilityPUETests(unittest.TestCase):
    def test_factor_and_conservative_fallback(self):
        self.assertEqual(observed_pue(10, 5), (1.5, False))
        self.assertEqual(observed_pue(1, 10), (3.0, False))
        self.assertEqual(observed_pue(None, 10), (1.0, True))
        self.assertEqual(observed_pue(0, 4), (1.0, True))
        for invalid in (-1.0, float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    observed_pue(invalid, 3)

    def test_name_to_dc_mapping_rejects_missing(self):
        centers = {"a": SimpleNamespace(dc_id=1),
                   "b": SimpleNamespace(dc_id=2)}
        factors, missing = observed_facility_multipliers(
            {"a": sample(10, 5), "b": sample(None, None)}, centers)
        self.assertEqual(factors, {1: 1.5, 2: 1.0})
        self.assertEqual(missing, 1)
        with self.assertRaises(AssertionError):
            observed_facility_multipliers({"a": sample(10, 5)}, centers)

    def test_initial_factor_is_one_and_step_updates_only_after_observation(self):
        policy = QueueAwareLaggedPUE(seed=901)
        control = QueueAwareIndexedTransit(seed=901)
        self.assertEqual((policy.population, policy.generations),
                         (control.population, control.generations))
        self.assertEqual(policy._facility_carbon_factor(3), 1.0)
        self.assertEqual(control._facility_carbon_factor(3), 1.0)
        policy.observe_facility_after_step(
            {"a": sample(10, 5)}, {"a": SimpleNamespace(dc_id=3)})
        self.assertEqual(policy._facility_carbon_factor(3), 1.5)
        self.assertEqual(policy.lagged_pue_observation_steps, 1)
        self.assertEqual(policy.lagged_pue_nonunit_site_readings, 1)
        self.assertEqual(control._facility_carbon_factor(3), 1.0)
        policy.reset()
        self.assertEqual(policy._facility_carbon_factor(3), 1.0)
        self.assertEqual(policy.lagged_pue_observation_steps, 0)


if __name__ == "__main__":
    unittest.main()
