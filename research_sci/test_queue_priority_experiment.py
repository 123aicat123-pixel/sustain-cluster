"""No-simulator invariants for fair FIFO-vs-EDF comparison."""
import unittest

from research_sci.queue_priority_experiment import pair_report


def example(queue_order):
    return {
        "seed":1,"capacity_scale":.02,"window_index":0,
        "queue_discipline":queue_order,
        "train_window_start":"train","train_admissions_end":"trainend",
        "test_window_start":"test","test_admissions_end":"testend",
        "test_tasks_admitted":5,"test_admission_signature":"same",
        "train_routing_signature":"same",
        "train_admission_signature":"same",
        "pretest_train_completed":10,"pretest_learned_buffer_minutes":50.,
        "applied_frozen_buffer_minutes":30.,
        "test_sla_met":2,"test_sla_violated":2,"test_tasks_finished":4,
        "test_finished_work_signature":"same_finished",
        "test_completed_core_minutes":120.,
        "test_deadline_failures_including_overdue":3,
        "test_unfinished":1,"test_unfinished_overdue":1,
        "test_total_carbon_kg":100.,
        "test_routing_signature":"same",
    }


class QueuePriorityExperimentTests(unittest.TestCase):
    def test_equal_work_yields_carbon_delta(self):
        f=example("fifo")
        e=example("edf")
        e["test_total_carbon_kg"]=90.
        e["test_sla_violated"]=1
        e["test_sla_met"]=3
        e["test_deadline_failures_including_overdue"]=2
        r=pair_report(f,e)
        self.assertTrue(r["same_completed_work_set"])
        self.assertAlmostEqual(r["carbon_difference_pct_if_same_work"],-10)
        self.assertEqual(r["sla_failure_delta_edf_minus_fifo"],-1)

    def test_different_job_identity_invalidates_carbon_claim(self):
        f=example("fifo")
        e=example("edf")
        e["test_finished_work_signature"]="different"
        r=pair_report(f,e)
        self.assertFalse(r["same_completed_work_set"])
        self.assertIsNone(r["carbon_difference_kg_if_same_work"])
        self.assertIsNone(r["carbon_difference_pct_if_same_work"])

    def test_same_admissions_required(self):
        f=example("fifo")
        e=example("edf")
        e["test_admission_signature"]="different"
        with self.assertRaises(AssertionError):
            pair_report(f,e)

    def test_no_outcome_conservation_failure(self):
        f=example("fifo")
        e=example("edf")
        e["test_sla_violated"]=100
        with self.assertRaises(AssertionError):
            pair_report(f,e)


if __name__=="__main__":
    unittest.main()
