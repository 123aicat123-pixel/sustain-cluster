"""Unit contracts for aggregate all-candidate feasibility audit."""
import unittest
from research_sci.action_feasibility_study import summarize


class AllCandidateStudyTests(unittest.TestCase):
    def sample(self):
        return {
            "seed":1,"capacity_scale":.02,"window_index":0,
            "test_tasks_admitted":5,"test_tasks_finished":4,
            "test_unfinished":1,"test_sla_violated":2,
            "test_deadline_failures_including_overdue":3,
            "test_action_feasibility":{
                "dispatches":5,"completed":4,"censored_unfinished":1,
                "observed_sla_misses_completed":2,
                "no_candidate_forecast":0,
                "no_unbuffered_feasible_center":3,
                "no_buffered_feasible_center":4,
                "chosen_unbuffered_predicted_late":4,
                "unbuffered_predicted_rescue_elsewhere":1,
                "unbuffered_predicted_rescue_and_actual_missed_completed":1,
                "buffered_predicted_rescue_elsewhere":0,
                "buffered_cheapest_intensity_selection_fraction_if_defined":.5,
            },
        }

    def test_valid_read_only_audit(self):
        result=summarize([self.sample()])
        r=result["per_seed_capacity_window"][0]
        self.assertEqual(r["predicted_alternative_while_chosen_late"],1)
        self.assertEqual(r["no_optimistically_feasible_center"],3)
        self.assertEqual(r["censored"],1)

    def test_missing_job_snapshot_rejected(self):
        row=self.sample()
        row["test_action_feasibility"]["dispatches"]=4
        with self.assertRaises(AssertionError):
            summarize([row])

    def test_actual_miss_counts_match_simulator(self):
        row=self.sample()
        row["test_action_feasibility"]["observed_sla_misses_completed"]=1
        with self.assertRaises(AssertionError):
            summarize([row])

    def test_no_false_sla_rescue_claim(self):
        result=summarize([self.sample()])
        self.assertIn("NOT proven SLA rescues",result["disclaimer"])


if __name__=="__main__":
    unittest.main()
