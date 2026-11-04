"""Capacity sensitivity checks that do not need simulator dependencies."""
import unittest
from research_sci.capacity_sensitivity import verify_scales,summarize_sensitivity


def r(scale,win,seed,policy,finished,work,carbon,misses):
    return {
        "capacity_scale":scale,"window_index":win,"seed":seed,
        "treatment":policy,"test_tasks_finished":finished,
        "test_tasks_admitted":20,"test_unfinished":20-finished,
        "test_unfinished_overdue":0,
        "test_finished_work_signature":work,
        "test_completed_core_minutes":finished*15,
        "test_total_carbon_kg":carbon,
        "test_deadline_failures_including_overdue":misses,
    }


class CapacitySensitivityTests(unittest.TestCase):
    def test_capacity_grid_is_predeclared_and_ordered(self):
        self.assertEqual(verify_scales([.02,.05,.1]),(.02,.05,.1))
        for invalid in ([.02,.02],[.2,.05],[0,.1],[.1,1.2],[.1]):
            with self.assertRaises(ValueError):
                verify_scales(invalid)

    def test_same_completed_work_allows_paired_carbon(self):
        rows=[r(.02,0,1,"fixed_30",20,"identical",100,8),
              r(.02,0,1,"fixed_60",20,"identical",90,7)]
        summary=summarize_sensitivity(rows,"fixed_60")
        self.assertEqual(len(summary),1)
        self.assertAlmostEqual(summary[0]["mean_carbon_delta_pct"],-10)

    def test_different_completed_identity_prohibits_carbon_claim(self):
        rows=[r(.02,0,1,"fixed_30",20,"taskA",100,8),
              r(.02,0,1,"fixed_60",20,"taskB",90,7)]
        summary=summarize_sensitivity(rows,"fixed_60")
        self.assertIsNone(summary[0]["mean_carbon_delta_pct"])
        self.assertFalse(summary[0]["all_seeds_same_completed_work"])
        self.assertEqual(summary[0]["mean_deadline_failure_delta"],-1)

    def test_incomplete_pair_fails(self):
        with self.assertRaises(AssertionError):
            summarize_sensitivity([r(.02,0,1,"fixed_30",20,"A",100,8)],"fixed_60")


if __name__=="__main__":
    unittest.main()
