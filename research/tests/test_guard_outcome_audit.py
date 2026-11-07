"""Contract checks for actual-outcome audit; negative results must be visible."""
import unittest
from research.guard_outcome_audit import audit_guard_runs


def run(policy, misses, carbon, cost, **kwargs):
    return dict(policy=policy, seed=501, tasks_dispatched=10, tasks_finished=10,
                unfinished_dispatched=0, fallback_assignments=0,
                lifecycle_conserved=True, sla_violated=misses, sla_met=10-misses,
                reported_total_carbon_kg=carbon,
                reported_total_cost_usd=cost, **kwargs)


class TestGuardOutcomeAudit(unittest.TestCase):
    def test_carbon_improves_but_sla_worsens_is_explicitly_unsafe(self):
        report=audit_guard_runs([
            run("queue_nsga2", 2, 100.0, 20.0),
            run("queue_nsga2_carbon_sla_guard", 4, 95.0, 19.0,
                carbon_guard_interventions=2, carbon_guard_vetoes=3),
        ])[0]
        self.assertEqual(report["guard_minus_reference_sla_misses"], 2)
        self.assertTrue(report["observed_nonincreasing_carbon"])
        self.assertFalse(report["observed_no_extra_sla_misses"])
        self.assertFalse(report["observed_three_objective_weak_dominance"])
        self.assertEqual(report["guard_risk_vetoes"], 3)

    def test_full_dominance_case(self):
        report=audit_guard_runs([
            run("queue_nsga2", 3, 100., 20.),
            run("queue_nsga2_carbon_sla_guard", 2, 99., 19.),
        ])[0]
        self.assertTrue(report["observed_three_objective_weak_dominance"])

    def test_partial_drain_is_not_ranked(self):
        g=run("queue_nsga2_carbon_sla_guard", 2, 99., 19.)
        g["unfinished_dispatched"]=1
        report=audit_guard_runs([run("queue_nsga2", 3, 100., 20.),g])[0]
        self.assertFalse(report["eligible"])
        self.assertNotIn("observed_no_extra_sla_misses",report)

    def test_duplicate_run_rejected(self):
        base=run("queue_nsga2", 2, 100., 20.)
        with self.assertRaises(ValueError):
            audit_guard_runs([base,base])


if __name__=="__main__":
    unittest.main()
