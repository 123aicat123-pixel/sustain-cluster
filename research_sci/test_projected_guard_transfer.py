"""No-simulator contracts for 4-way locked guard transfer accounting."""
import unittest
from research_sci.projected_guard_transfer import evaluate_group,METHODS,transfer


def example(name):
    r={
        "batch_planner":name,"seed":1,"capacity_scale":.1,
        "calendar_month":11,"calendar_day":1,"window_index":0,
        "test_window_start":"later","test_admissions_end":"later_end",
        "train_window_start":"prior","train_admissions_end":"prior_end",
        "test_tasks_admitted":10,"test_admission_signature":"identical",
        "train_routing_signature":"empty","train_admission_signature":"empty",
        "pretest_train_completed":0,"pretest_train_forecast_residuals":0,
        "applied_frozen_buffer_minutes":30.0,
        "fixed_policy_without_calibration":True,
        "queue_discipline":"fifo","forecast_queue_discipline":"fifo",
        "test_sla_met":8,"test_sla_violated":1,"test_tasks_finished":9,
        "test_unfinished":1,"test_unfinished_overdue":1,
        "test_deadline_failures_including_overdue":2,
        "test_finished_work_signature":"same",
        "test_total_carbon_kg":100.0,
        "test_routing_signature":"a",
        "test_guard_reviewed_batches":2 if name.startswith("guard") else 0,
        "test_guard_accepted_batches":1 if name.startswith("guard") else 0,
        "test_guard_rejected_risk":1 if name.startswith("guard") else 0,
        "test_guard_rejected_no_gain":0,
        "test_guard_rejected_forced":0,
        "test_guard_projected_carbon_delta_accepted":-2.,
        "test_joint_batch_plans":1 if name.startswith("guard") else
            (2 if name=="beam4" else 0),
    }
    return r


class GuardTransferTests(unittest.TestCase):
    def test_four_complete_arms_and_comparable_carbon(self):
        rows=[example(name) for name in METHODS]
        rows[2]["test_sla_met"]=9
        rows[2]["test_sla_violated"]=0
        rows[2]["test_deadline_failures_including_overdue"]=1
        rows[2]["test_total_carbon_kg"]=98.0
        result=evaluate_group(rows)
        self.assertEqual(len(result),4)
        self.assertEqual(result[2]["sla_delta_vs_greedy"],-1)
        self.assertAlmostEqual(result[2]["carbon_delta_pct_if_identical_work"],-2)
        self.assertEqual(result[2]["guard_accepted_batches"],1)

    def test_work_mismatch_gates_carbon(self):
        rows=[example(name) for name in METHODS]
        rows[3]["test_finished_work_signature"]="different"
        self.assertIsNone(evaluate_group(rows)[3]["carbon_delta_pct_if_identical_work"])

    def test_reject_admission_mismatch_and_missing_arm(self):
        rows=[example(name) for name in METHODS]
        rows[1]["test_admission_signature"]="wrong"
        with self.assertRaises(AssertionError):evaluate_group(rows)
        with self.assertRaises(AssertionError):evaluate_group(rows[:3])

    def test_reject_guard_accounting_inconsistency(self):
        rows=[example(name) for name in METHODS]
        rows[2]["test_guard_accepted_batches"]=2
        with self.assertRaises(AssertionError):evaluate_group(rows)

    def test_guard_must_have_no_local_training(self):
        rows=[example(name) for name in METHODS]
        rows[1]["pretest_train_completed"]=1
        with self.assertRaises(AssertionError):evaluate_group(rows)

    def test_no_retesting_used_september_october(self):
        with self.assertRaises(ValueError):
            transfer(9,1,[1,42],[.02,.1],(288,448),"/tmp/ignored.json")

if __name__=="__main__":
    unittest.main()
