"""Power/CI decomposition must reconcile all measured carbon changes."""
import unittest
from research.facility_power_carbon_attribution import decompose_power_carbon


def cell(policy, dc, it, hvac, ci, energy=None, step=0):
    total = it + hvac
    if energy is None:
        energy = total / 4
    return dict(seed=3, policy=policy, step_index=step, dc_name=dc,
                it_power_kw=it, hvac_power_kw=hvac, total_dc_power_kw=total,
                energy_kwh=energy, effective_ci_g_per_kwh=ci,
                carbon_kg=energy*ci/1000)


class TestPowerCarbonAttribution(unittest.TestCase):
    def test_it_hvac_decomposition(self):
        b=cell("base","A",20,8,300)
        t=cell("trial","A",16,12,300)
        out=decompose_power_carbon([b,t],reference="base",candidate="trial")[0]["total"]
        self.assertAlmostEqual(out["it_carbon_kg"],-0.3)
        self.assertAlmostEqual(out["hvac_carbon_kg"],0.3)
        self.assertAlmostEqual(out["delta_carbon_kg"],0)
        self.assertAlmostEqual(out["grid_adjustment_carbon_kg"],0)

    def test_lower_energy_with_higher_ci_and_residual(self):
        b=cell("base","A",20,8,200,energy=8)
        t=cell("trial","A",16,8,400,energy=7)
        out=decompose_power_carbon([b,t],reference="base",candidate="trial")[0]["total"]
        self.assertAlmostEqual(out["delta_energy_kwh"],-1)
        self.assertAlmostEqual(out["delta_carbon_kg"],1.2)
        self.assertAlmostEqual(sum(out[k] for k in (
            "it_carbon_kg","hvac_carbon_kg",
            "grid_adjustment_carbon_kg","effective_ci_carbon_kg")),1.2)

    def test_reject_invalid_power_identity(self):
        b=cell("base","A",10,5,200)
        t=dict(cell("trial","A",8,5,200),total_dc_power_kw=99)
        with self.assertRaises(AssertionError):
            decompose_power_carbon([b,t],reference="base",candidate="trial")

    def test_reject_missing_cells(self):
        b=cell("base","A",10,5,200)
        t=cell("trial","B",10,5,200)
        with self.assertRaises(AssertionError):
            decompose_power_carbon([b,t],reference="base",candidate="trial")

    def test_reject_duplicates(self):
        b=cell("base","A",10,5,200)
        t=cell("trial","A",10,5,200)
        with self.assertRaises(AssertionError):
            decompose_power_carbon([b,t,b],reference="base",candidate="trial")


if __name__=="__main__":
    unittest.main()
