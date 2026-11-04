"""Behavioral evidence for the reward objectives bundled with SustainCluster.

These are CHARACTERIZATION TESTS of the *current* code. They prove what the
reward components read, not whether the numerical surrogate is scientifically
appropriate. The tests intentionally avoid needing the expensive simulator.
"""
import unittest
from types import SimpleNamespace

from rewards.predefined.energy_price_reward import EnergyPriceReward
from rewards.predefined.carbon_emissions_reward import CarbonEmissionsReward


def dummy_task(price=100.0, carbon_g_per_kwh=400.0):
    dc = SimpleNamespace(
        price_manager=SimpleNamespace(get_current_price=lambda: price),
        ci_manager=SimpleNamespace(get_current_ci=lambda norm=False: carbon_g_per_kwh),
    )
    return SimpleNamespace(dest_dc=dc, cores_req=10, duration=30)


class TestRewardSignalContracts(unittest.TestCase):
    def setUp(self):
        self.low_cluster_metrics = {
            "datacenter_infos": {
                "DC1": {"__common__": {
                    "energy_cost_USD": 0.1, "carbon_emissions_kg": 0.2,
                    "__sla__": {"met": 1, "violated": 0},
                }}
            },
            "transmission_cost_total_usd": 0.0,
            "transmission_emissions_total_kg": 0.0,
        }
        self.high_cluster_metrics = {
            "datacenter_infos": {
                "DC1": {"__common__": {
                    "energy_cost_USD": 900.0, "carbon_emissions_kg": 800.0,
                    "__sla__": {"met": 0, "violated": 1},
                }}
            },
            "transmission_cost_total_usd": 800.0,
            "transmission_emissions_total_kg": 700.0,
        }

    def test_energy_price_reward_ignores_actual_simulation_cost(self):
        score = EnergyPriceReward()
        task = dummy_task()
        a = score(self.low_cluster_metrics, [task], None)
        b = score(self.high_cluster_metrics, [task], None)
        self.assertEqual(a, b)
        self.assertAlmostEqual(a, -0.03)  # 10 * 30 / 10000 * $100 / 100

    def test_carbon_reward_ignores_actual_simulation_emissions(self):
        score = CarbonEmissionsReward()
        task = dummy_task()
        a = score(self.low_cluster_metrics, [task], None)
        b = score(self.high_cluster_metrics, [task], None)
        self.assertEqual(a, b)
        self.assertAlmostEqual(a, -0.12)  # (10 * 30 / 10000 * 400) / 100

    def test_energy_price_proxy_changes_with_dc_price_not_measured_cost(self):
        score = EnergyPriceReward()
        cheap = score(self.low_cluster_metrics, [dummy_task(price=100)], None)
        dear = score(self.low_cluster_metrics, [dummy_task(price=200)], None)
        self.assertAlmostEqual(dear, 2 * cheap)

    def test_carbon_proxy_changes_with_dc_carbon_not_measured_emissions(self):
        score = CarbonEmissionsReward()
        clean = score(self.low_cluster_metrics, [dummy_task(carbon_g_per_kwh=100)], None)
        dirty = score(self.low_cluster_metrics, [dummy_task(carbon_g_per_kwh=500)], None)
        self.assertAlmostEqual(dirty, 5 * clean)

    def test_both_rewards_zero_when_task_list_empty_despite_simulation_costs(self):
        for strategy in (EnergyPriceReward(), CarbonEmissionsReward()):
            with self.subTest(strategy=type(strategy).__name__):
                self.assertEqual(strategy(self.high_cluster_metrics, [], None), 0.0)

    def test_both_rewards_ignore_sla_and_transmission_cost(self):
        task = dummy_task()
        for strategy in (EnergyPriceReward(), CarbonEmissionsReward()):
            with self.subTest(strategy=type(strategy).__name__):
                self.assertEqual(
                    strategy(self.low_cluster_metrics, [task], None),
                    strategy(self.high_cluster_metrics, [task], None),
                )


if __name__ == "__main__":
    unittest.main()
