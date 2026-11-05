"""Contracts for locked historical-to-new-calendar generalization."""
import unittest
from research_sci.calendar_transfer import audit_transfer,run_transfer,METHODS


def record(method):
    return {
        "batch_planner":method,"seed":1,"capacity_scale":.1,
        "calendar_month":9,"calendar_day":1,"window_index":0,
        "fixed_policy_without_calibration":True,
        "pretest_train_forecast_residuals":0,
        "test_window_start":"new_test","test_admissions_end":"end",
        "train_window_start":"new_train","train_admissions_end":"end_train",
        "test_tasks_admitted":10,"test_admission_signature":"same_jobs",
        "train_routing_signature":"same_training",
        "train_admission_signature":"same_prefix",
        "pretest_train_completed":0,"pretest_learned_buffer_minutes":30.,
        "applied_frozen_buffer_minutes":30.,
        "queue_discipline":"fifo","forecast_queue_discipline":"fifo",
        "test_sla_met":7,"test_sla_violated":2,"test_tasks_finished":9,
        "test_unfinished":1,"test_unfinished_overdue":1,
        "test_deadline_failures_including_overdue":3,
        "test_finished_work_signature":"same_completed",
        "test_total_carbon_kg":100.,
        "test_routing_signature":"route",
        "test_gate_batches":0 if method!="gate50" else 2,
        "test_gate_activated_batches":0 if method!="gate50" else 1,
        "test_gate_tasks":0 if method!="gate50" else 10,
        "test_gate_feasible_tasks":0 if method!="gate50" else 7,
        "test_joint_batch_plans":0 if method=="greedy" else 2,
    }


class CalendarTransferTests(unittest.TestCase):
    def test_comparison_pairs_three_predeclared_methods(self):
        rows=[record(t) for t in METHODS]
        rows[2]["test_sla_violated"]=1
        rows[2]["test_sla_met"]=8
        rows[2]["test_deadline_failures_including_overdue"]=2
        rows[2]["test_total_carbon_kg"]=97.
        r=audit_transfer(rows)
        self.assertEqual(len(r),3)
        self.assertEqual(r[2]["sla_delta_vs_greedy"],-1)
        self.assertAlmostEqual(r[2]["carbon_change_pct_if_identical_work"],-3)
        self.assertEqual(r[2]["gate_activated_batches"],1)

    def test_missing_arm_and_different_arrivals_rejected(self):
        with self.assertRaises(AssertionError):
            audit_transfer([record("greedy"),record("beam4")])
        rows=[record(t) for t in METHODS]
        rows[1]["test_admission_signature"]="different_jobs"
        with self.assertRaises(AssertionError):
            audit_transfer(rows)

    def test_completions_changed_blocks_carbon_claim(self):
        rows=[record(t) for t in METHODS]
        rows[2]["test_finished_work_signature"]="different"
        results=audit_transfer(rows)
        self.assertIsNone(results[2]["carbon_change_pct_if_identical_work"])

    def test_fixed_policy_is_training_free_in_all_arms(self):
        rows=[record(t) for t in METHODS]
        self.assertTrue(all(x["fixed_policy_without_calibration"] for x in rows))
        self.assertEqual({x["pretest_train_completed"] for x in rows},{0})
        self.assertEqual({x["pretest_train_forecast_residuals"] for x in rows},{0})

    def test_reject_existing_august_as_new_holdout(self):
        with self.assertRaises(ValueError):
            run_transfer(8,1,[1,42],[.02,.1],(288,448),"/tmp/ignored.json")

if __name__=="__main__":
    unittest.main()
