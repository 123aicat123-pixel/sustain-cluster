"""Dataset-free checks of state-risk study completeness and censoring."""
import unittest
from research_sci.state_risk_study import analyze_pressure


class StudyTests(unittest.TestCase):
    def sample(self):
        group={
            "under_50pct":{"dispatches":3,"completed":2,
                           "censored_unfinished":1,"forecast_evaluable":2},
            "at_least_80pct":{"dispatches":2,"completed":2,
                              "censored_unfinished":0,"forecast_evaluable":2},
        }
        return {
            "seed":1,"capacity_scale":.02,"window_index":0,
            "test_tasks_admitted":5,"test_tasks_finished":4,
            "test_unfinished":1,"test_deadline_failures_including_overdue":2,
            "test_state_risk_total":{
                "dispatches":5,"completed":4,"censored_unfinished":1,
                "forecast_evaluable":4,
                "forecast_mae_minutes":15.,
                "forecast_signed_optimism_minutes":12.,
                "forecast_p90_absolute_error_minutes":25.,
            },
            "test_state_risk_by_pressure":{
                "cpu_utilization":group,
                "pending_queue":{"empty":{"dispatches":5}},
                "committed_inbound":{"none":{"dispatches":5}},
                "predicted_sla_slack":{"0_to_60min":{"dispatches":5}},
            },
        }

    def test_valid(self):
        result=analyze_pressure([self.sample()])
        self.assertEqual(result["experiment_rows"],1)
        self.assertEqual(result["per_seed_capacity_window"][0]["censored_unfinished"],1)

    def test_missing_state_record_rejected(self):
        x=self.sample()
        x["test_state_risk_total"]["dispatches"]=4
        with self.assertRaises(AssertionError):
            analyze_pressure([x])

    def test_censoring_mismatch_rejected(self):
        x=self.sample()
        x["test_state_risk_total"]["censored_unfinished"]=0
        with self.assertRaises(AssertionError):
            analyze_pressure([x])

    def test_missing_predeclared_pressure_bin_rejected(self):
        x=self.sample()
        x["test_state_risk_by_pressure"]["pending_queue"]["empty"]["dispatches"]=4
        with self.assertRaises(AssertionError):
            analyze_pressure([x])


if __name__=="__main__":
    unittest.main()
