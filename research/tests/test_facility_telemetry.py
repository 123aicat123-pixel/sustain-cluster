"""Facility cell accounting / paired carbon decomposition regression tests."""
import unittest

from research.facility_telemetry import (
    facility_cell, paired_carbon_attribution, verify_facility_telemetry
)


def row(seed,policy,step,dc,energy,ci,price=100):
    return {
        "seed":seed,"policy":policy,"step_index":step,"dc_name":dc,
        "energy_kwh":energy,"effective_ci_g_per_kwh":ci,
        "carbon_kg":energy*ci/1000,"cost_usd":energy*price/1000,
        "price_usd_per_mwh":price,"source_ci_g_per_kwh":ci,
    }


def summary(policy,cells):
    return dict(seed=7,policy=policy,steps_completed=2,
                facility_energy_kwh=sum(c["energy_kwh"] for c in cells),
                facility_carbon_kg=sum(c["carbon_kg"] for c in cells),
                facility_cost_usd=sum(c["cost_usd"] for c in cells))


class TestFacilityTelemetry(unittest.TestCase):
    def setUp(self):
        self.base=[row(7,"base",i,"A",100,300) for i in (0,1)]
        self.trial=[row(7,"trial",0,"A",90,400),
                    row(7,"trial",1,"A",90,300)]

    def test_identity_energy_down_carbon_up(self):
        reports=paired_carbon_attribution(self.base+self.trial,
                                          reference="base",candidate="trial")
        total=reports[0]["total"]
        self.assertEqual(total["energy_delta_kwh"],-20)
        self.assertAlmostEqual(total["carbon_delta_kg"],3)
        self.assertAlmostEqual(total["energy_effect_carbon_kg"],-6)
        self.assertAlmostEqual(total["effective_ci_effect_carbon_kg"],9)

    def test_complete_lattice_reconciles(self):
        audit=verify_facility_telemetry(
            self.base+self.trial,[summary("base",self.base),summary("trial",self.trial)])
        self.assertEqual(len(audit),2)
        self.assertEqual(audit[0]["cells"],2)

    def test_missing_cell_is_fatal(self):
        with self.assertRaises(AssertionError):
            verify_facility_telemetry(
                self.base+self.trial[:1],
                [summary("base",self.base),summary("trial",self.trial)])

    def test_duplicate_cell_is_fatal(self):
        with self.assertRaises(AssertionError):
            paired_carbon_attribution(
                self.base+self.trial+self.base[:1],reference="base",candidate="trial")

    def test_misaligned_centers_rejected(self):
        other=[dict(r,dc_name="B") for r in self.trial]
        with self.assertRaises(AssertionError):
            paired_carbon_attribution(self.base+other,
                                      reference="base",candidate="trial")

    def test_real_step_fields(self):
        info={
            "__common__":{"energy_consumption_kwh":2.0,
                          "carbon_emissions_kg":0.6,
                          "energy_cost_USD":0.2,
                          "price_USD_kwh":100,
                          "ci":310,"running_tasks":2,"pending_tasks":1},
            "agent_bat":{"bat_avg_CI":300},
            "agent_dc":{"dc_ITE_total_power_kW":5,
                        "dc_HVAC_total_power_kW":3,
                        "dc_total_power_kW":8}
        }
        r=facility_cell(seed=7,policy="p",step_index=0,
                        dc_name="California",dc_info=info)
        self.assertEqual(r["carbon_kg"],0.6)
        self.assertEqual(r["it_power_kw"],5)
        self.assertEqual(r["hvac_power_kw"],3)


if __name__=="__main__":
    unittest.main()
