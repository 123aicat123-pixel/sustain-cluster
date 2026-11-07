"""Unit tests for accounting decomposition without simulator dependencies."""
import unittest
from research.queue_carbon_diagnostics import analyze


def row(seed, policy, *, facility_cost=10, network_cost=2,
        facility_carbon=100, network_carbon=4, violated=2, remote=1,
        complete=True, fallback=0):
    return {
        "seed": seed, "policy": policy,
        "fully_drained": complete, "fallback_assignments": fallback,
        "tasks_dispatched": 10, "tasks_finished": 10 if complete else 9,
        "facility_cost_usd": facility_cost,
        "transmission_cost_usd": network_cost,
        "reported_total_cost_usd": facility_cost + network_cost,
        "facility_carbon_kg": facility_carbon,
        "transmission_carbon_kg": network_carbon,
        "reported_total_carbon_kg": facility_carbon + network_carbon,
        "remote_dispatches": remote, "local_dispatches": 10-remote,
        "sla_violated": violated,
    }


class TestDecomposition(unittest.TestCase):
    def test_facility_and_network_attribution_reconciles(self):
        records=[
            row(1,"base"),
            row(1,"new",facility_cost=9,network_cost=4,
                facility_carbon=99,network_carbon=10,
                remote=3,violated=0),
        ]
        analysis=analyze(records,reference="base")
        x=next(x for x in analysis["results"] if x["policy"]=="new")
        self.assertTrue(x["eligible"])
        self.assertAlmostEqual(x["delta_total_cost_usd"],1)
        self.assertAlmostEqual(x["delta_total_carbon_kg"],5)
        self.assertEqual(x["delta"]["sla_violated"],-2)

    def test_refuses_censored_ranking(self):
        rows=[row(1,"base"),row(1,"new",complete=False)]
        result=analyze(rows,reference="base")
        self.assertEqual(len(result["unusable"]),1)
        self.assertIsNone(result["mean_deltas"]["new"])

    def test_detects_broken_accounting(self):
        x=row(1,"new")
        x["reported_total_carbon_kg"]+=5
        with self.assertRaisesRegex(AssertionError,"carbon"):
            analyze([row(1,"base"),x],reference="base")

    def test_unequal_cohort_fails_eligibility(self):
        base=row(1,"base")
        updated=row(1,"new")
        updated["tasks_dispatched"]=11
        updated["tasks_finished"]=11
        result=analyze([base,updated],reference="base")
        self.assertFalse(result["results"][1]["eligible"])

    def test_duplicate_seed_policy_rejected(self):
        with self.assertRaisesRegex(ValueError,"repeated"):
            analyze([row(1,"base"),row(1,"base")],reference="base")


if __name__=="__main__":
    unittest.main()
