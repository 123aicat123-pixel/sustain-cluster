"""Facility energy/cost/carbon accounting cross-checks."""
import unittest
from research.physical_accounting import validate_datacenter_step


class TestFacilityAccounting(unittest.TestCase):
    def sample(self):
        return {
            "agent_bat": {"bat_avg_CI": 250.0},
            "__common__": {
                "energy_consumption_kwh": 10.0,
                "price_USD_kwh": 140.0,  # simulator treats this as USD/MWh
                "energy_cost_USD": 1.4,
                "carbon_emissions_kg": 2.5,
            },
        }

    def test_coherent_metrics(self):
        values = validate_datacenter_step(self.sample())
        self.assertAlmostEqual(values["facility_cost_usd"], 1.4)
        self.assertAlmostEqual(values["facility_carbon_kg"], 2.5)

    def test_bad_carbon_is_detected(self):
        info = self.sample()
        info["__common__"]["carbon_emissions_kg"] = 3.0
        with self.assertRaisesRegex(AssertionError, "carbon"):
            validate_datacenter_step(info)

    def test_bad_cost_is_detected(self):
        info = self.sample()
        info["__common__"]["energy_cost_USD"] = 4.0
        with self.assertRaisesRegex(AssertionError, "cost"):
            validate_datacenter_step(info)

    def test_negative_energy_rejected(self):
        info = self.sample()
        info["__common__"]["energy_consumption_kwh"] = -10.0
        with self.assertRaisesRegex(AssertionError, "negative"):
            validate_datacenter_step(info)


if __name__ == "__main__":
    unittest.main()
