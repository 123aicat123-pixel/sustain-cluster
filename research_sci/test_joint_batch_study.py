"""No third-party dependencies for paired joint batch research contracts."""
import unittest
from research_sci.joint_batch_study import compare_pair


def row(planner):
    return {
        "seed":1,"capacity_scale":.02,"window_index":0,
        "test_window_start":"t","test_admissions_end":"u",
        "train_window_start":"cal","train_admissions_end":"calend",
        "test_tasks_admitted":10,"test_admission_signature":"same",
        "train_routing_signature":"same",
        "train_admission_signature":"same",
        "pretest_train_completed":10,"pretest_learned_buffer_minutes":40,
        "applied_frozen_buffer_minutes":30,
        "queue_discipline":"fifo","forecast_queue_discipline":"fifo",
        "batch_planner":planner,
        "test_joint_batch_plans":0 if planner=="greedy" else 2,
        "test_joint_beam_expansions":0 if planner=="greedy" else 12,
        "test_joint_chunks":0 if planner=="greedy" else 4,
        "test_sla_met":5,"test_sla_violated":4,"test_tasks_finished":9,
        "test_unfinished":1,"test_unfinished_overdue":1,
        "test_deadline_failures_including_overdue":5,
        "test_finished_work_signature":"same",
        "test_total_carbon_kg":100.,
        "test_routing_signature":"same_route",
    }


class JointPairTests(unittest.TestCase):
    def test_comparable_same_completed_work(self):
        x,y=row("greedy"),row("beam4")
        y["test_total_carbon_kg"]=90.
        y["test_sla_met"]=6
        y["test_sla_violated"]=3
        y["test_deadline_failures_including_overdue"]=4
        r=compare_pair(x,y)
        self.assertTrue(r["identical_completed_work"])
        self.assertAlmostEqual(r["carbon_delta_pct_if_identical_work"],-10)
        self.assertEqual(r["deadline_failure_delta"],-1)

    def test_incomparable_finished_sets_null_carbon_delta(self):
        x,y=row("greedy"),row("beam4")
        y["test_finished_work_signature"]="different"
        r=compare_pair(x,y)
        self.assertIsNone(r["carbon_delta_pct_if_identical_work"])

    def test_admission_signature_mismatch_rejected(self):
        x,y=row("greedy"),row("beam4")
        y["test_admission_signature"]="different"
        with self.assertRaises(AssertionError): compare_pair(x,y)

    def test_joint_algorithm_must_execute(self):
        x,y=row("greedy"),row("beam4")
        y["test_joint_batch_plans"]=0
        with self.assertRaises(AssertionError): compare_pair(x,y)

if __name__=="__main__":
    unittest.main()
