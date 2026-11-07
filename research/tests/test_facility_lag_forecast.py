"""Lag feature isolation, split leakage and fixed ridge model contracts."""
import unittest
from research.facility_lag_forecast import (
    make_pairs, fit_models, predict, evaluate, split_digest
)

def r(day,seed,dc,step,energy,ci=200):
    return dict(scenario_date=day,seed=seed,dc_name=dc,
                policy="queue_nsga2_with_transit",step_index=step,
                energy_kwh=energy,carbon_kg=energy*ci/1000,
                it_power_kw=8+step,hvac_power_kw=5,
                dc_cpu_workload_fraction=0.2,
                running_tasks=2,pending_tasks=0,ambient_temp_c=24,
                effective_ci_g_per_kwh=ci,source_ci_g_per_kwh=ci)


class FacilityLagTests(unittest.TestCase):
    def setUp(self):
        self.rows=[r(day,seed,dc,t,energy=10+0.5*t)
                   for day in ("06-15","11-12","03-09")
                   for seed in (901,1701)
                   for dc in ("A","B")
                   for t in range(17)]

    def test_target_mutation_does_not_change_current_features(self):
        pairs=make_pairs(self.rows)
        key=lambda p:(p["scenario_date"],p["seed"],p["dc_name"],p["step_index"])
        before={key(p):p for p in pairs}
        changed=[dict(x) for x in self.rows]
        for row in changed:
            if row["scenario_date"]=="03-09" and row["step_index"]==9:
                row.update(energy_kwh=10000,carbon_kg=2000,
                           it_power_kw=999999,source_ci_g_per_kwh=999,
                           effective_ci_g_per_kwh=999)
        after={key(p):p for p in make_pairs(changed)}
        for k,p in before.items():
            if k[-1]==9 and k[0]=="03-09":
                self.assertEqual(p["x"],after[k]["x"])
                self.assertNotEqual(p["energy"],after[k]["energy"])
                self.assertNotEqual(p["carbon"],after[k]["carbon"])

    def test_holdout_target_or_features_do_not_change_training_coefficients(self):
        pairs=make_pairs(self.rows)
        train={"06-15","11-12"}
        model=fit_models(pairs,train)
        mutated=[dict(x) for x in self.rows]
        for x in mutated:
            if x["scenario_date"]=="03-09":
                x.update(energy_kwh=10000.0,carbon_kg=3000.0)
        other=fit_models(make_pairs(mutated),train)
        self.assertEqual(model,other)
        self.assertTrue(all(x["training_pairs"]==64 for x in model.values()))

    def test_no_cross_run_or_dc_lag(self):
        p=make_pairs(self.rows)
        self.assertEqual(len(p),3*2*2*16)
        self.assertEqual({x["step_index"] for x in p},set(range(1,17)))
        self.assertEqual(len(split_digest(p,{"06-15"})),64)

    def test_missing_step_rejected(self):
        rows=[x for x in self.rows if not
              (x["scenario_date"]=="06-15" and x["dc_name"]=="A"
               and x["seed"]==901 and x["step_index"]==4)]
        with self.assertRaises(AssertionError):
            make_pairs(rows)

    def test_forecast_finite_and_nonnegative(self):
        pairs=make_pairs(self.rows)
        models=fit_models(pairs,{"06-15","11-12"})
        outputs=evaluate(pairs,models,dates={"03-09"})
        self.assertEqual(len(outputs),4)
        for p in pairs:
            x=predict(models,p)
            self.assertGreaterEqual(x["ridge_energy"],0)
            self.assertGreaterEqual(x["ridge_carbon"],0)


if __name__=="__main__":
    unittest.main()
