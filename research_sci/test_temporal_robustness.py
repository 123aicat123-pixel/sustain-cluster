"""Contract tests for two predeclared chronological held-out windows."""
import unittest
from research_sci.temporal_robustness import planned_folds, window_summary


def row(seed,treatment,carbon,misses,finished=20):
    return {
        "seed":seed,"treatment":treatment,"test_total_carbon_kg":carbon,
        "test_deadline_failures_including_overdue":misses,
        "test_tasks_finished":finished,"test_tasks_admitted":20,
        "test_unfinished":20-finished,"test_unfinished_overdue":0,
        "test_finished_work_signature":f"tasks-{finished}",
        "test_completed_core_minutes":finished*15.0,
    }


class TemporalRobustnessTests(unittest.TestCase):
    def test_planned_windows_no_overlap(self):
        p=planned_folds()
        self.assertEqual([x["test_start_tick"] for x in p["test_windows"]],[288,448])
        self.assertEqual([x["test_gap_steps"] for x in p["test_windows"]],[272,432])
        self.assertEqual(p["fixed_sim_duration_days"],7)

    def test_reject_window_overlapping_prior_drain(self):
        with self.assertRaises(ValueError):
            planned_folds(test_starts=(288,370))
        with self.assertRaises(ValueError):
            planned_folds(test_starts=(288,288))
        with self.assertRaises(ValueError):
            planned_folds(test_starts=(288,600))

    def test_detect_same_seeds_different_test_results(self):
        rows=[row(1,"fixed_30",100,8),row(1,"fixed_60",90,7),
              row(42,"fixed_30",200,5),row(42,"fixed_60",220,6)]
        out=window_summary(rows,"fixed_60",1)
        self.assertFalse(out["both_objectives_nonworse_for_every_seed"])
        self.assertFalse(out["mean_carbon_lower_and_mean_deadline_failures_nonworse"])
        self.assertAlmostEqual(out["mean_carbon_delta_pct"],0)
        self.assertEqual(out["mean_deadline_failure_delta"],0)

    def test_unequal_completed_blocks_carbon_comparison(self):
        rows=[row(1,"fixed_30",100,8),row(1,"fixed_60",90,7,finished=19)]
        out=window_summary(rows,"fixed_60",0)
        self.assertFalse(out["all_seeds_same_completed_work"])
        self.assertIsNone(out["mean_carbon_delta_pct"])
        self.assertIsNone(out["paired_results"][0]["carbon_change_pct"])
        self.assertIsNone(out["paired_results"][0]["carbon_change_kg_if_comparable"])
        self.assertEqual(out["paired_results"][0]["reference_completed"], 20)
        self.assertEqual(out["paired_results"][0]["chosen_completed"], 19)

    def test_same_count_different_tasks_block_carbon_comparison(self):
        a=row(1,"fixed_30",100,8)
        b=row(1,"fixed_60",90,7)
        b["test_finished_work_signature"]="different jobs"
        out=window_summary([a,b],"fixed_60",0)
        self.assertFalse(out["all_seeds_same_completed_work"])
        self.assertFalse(out["paired_results"][0]["same_completed_task_identity"])
        self.assertTrue(out["paired_results"][0]["same_completed_count"])
        self.assertIsNone(out["paired_results"][0]["carbon_change_pct"])

    def test_no_missing_seed_or_treatment(self):
        with self.assertRaises(AssertionError):
            window_summary([row(1,"fixed_30",100,8)],"fixed_60",0)

    def test_identity_selection_still_valid(self):
        out=window_summary([row(1,"fixed_30",100,8)],"fixed_30",0)
        self.assertTrue(out["all_seeds_same_completed_work"])
        self.assertEqual(out["mean_carbon_delta_pct"],0)
        self.assertFalse(out["mean_carbon_lower_and_mean_deadline_failures_nonworse"])


if __name__=="__main__":
    unittest.main()
