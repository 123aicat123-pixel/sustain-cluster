"""No-data tests: paired controls and honest risk/carbon reporting."""
import copy
import unittest
from unittest.mock import patch

from research_sci.risk_frontier import (
    TREATMENTS, frozen_buffer_for_treatment, run_sweep,
    summarize_frontier, validate_paired,
)


def example(seed, treatment):
    margin = frozen_buffer_for_treatment(treatment, 225)
    safe = 0 if margin > 120 else (15 if margin > 30 else 25)
    misses = {"fixed_30": 30, "fixed_60": 28,
              "fixed_120": 27, "precalibrated_frozen": 26}[treatment]
    carbon = {"fixed_30": 100, "fixed_60": 110,
              "fixed_120": 125, "precalibrated_frozen": 135}[treatment]
    return {
        "seed": seed, "treatment": treatment,
        "capacity_scale": .02,
        "calibration_steps": 16, "gap_steps": 128,
        "test_steps": 16, "drain_steps": 96,
        "train_window_start": "2023-08-01",
        "train_admissions_end": "2023-08-01T04",
        "test_window_start": "2023-08-02T12",
        "test_admissions_end": "2023-08-02T16",
        "pretest_train_completed": 417,
        "pretest_train_forecast_residuals": 417,
        "pretest_learned_buffer_minutes": 225,
        "train_routing_signature": "trainhash",
        "train_admission_signature": "trainadmissions",
        "test_admission_signature": "testadmissions",
        "test_tasks_admitted": 100,
        "test_tasks_finished": 100,
        "test_unfinished": 0,
        "test_unfinished_overdue": 0,
        "test_sla_met": 100 - misses,
        "test_sla_violated": misses,
        "test_deadline_failures_including_overdue": misses,
        "test_total_carbon_kg": carbon + seed,
        "applied_frozen_buffer_minutes": margin,
        "test_decision_margin_predicted_safe_completed": safe,
        "test_decision_margin_false_safe_completed": min(3, safe),
        "test_safe_flag_is_vacuous": safe == 0,
    }


def rows():
    return [example(seed, treatment) for seed in (1, 42)
            for treatment in TREATMENTS]


class FrontierTests(unittest.TestCase):
    def test_predeclared_buffers(self):
        self.assertEqual(frozen_buffer_for_treatment("fixed_30", 225), 30)
        self.assertEqual(frozen_buffer_for_treatment("fixed_60", 225), 60)
        self.assertEqual(frozen_buffer_for_treatment("fixed_120", 225), 120)
        self.assertEqual(
            frozen_buffer_for_treatment("precalibrated_frozen", 225), 225)
        with self.assertRaises(ValueError):
            frozen_buffer_for_treatment("fixed_999", 225)

    def test_complete_paired_frontier(self):
        data = summarize_frontier(rows())
        self.assertEqual(data["seeds"], [1, 42])
        self.assertEqual(len(data["treatments"]), len(TREATMENTS))
        learned = next(v for v in data["treatments"]
                       if v["treatment"] == "precalibrated_frozen")
        self.assertEqual(learned["mean_deadline_failures"], 26)
        self.assertEqual(learned["pooled_safe_prediction_fraction_admitted"], 0)
        self.assertIsNone(learned["pooled_false_safe_rate_if_defined"])
        self.assertFalse(learned["has_nonvacuous_safe_predictions"])
        self.assertTrue(learned["equal_completed_work_to_fixed_30"])

    def test_mismatched_admissions_fail_fast(self):
        data = rows()
        data[1]["test_admission_signature"] = "different"
        with self.assertRaises(AssertionError):
            validate_paired(data)

    def test_incomplete_treatment_set_fails(self):
        with self.assertRaises(ValueError):
            validate_paired(rows()[:-1])

    def test_unequal_completed_is_not_claimed_comparable(self):
        data = rows()
        data[1]["test_tasks_finished"] = 99
        data[1]["test_unfinished"] = 1
        data[1]["test_sla_met"] -= 1
        data[1]["test_unfinished_overdue"] = 0
        summary = summarize_frontier(data)
        fixed60 = next(v for v in summary["treatments"]
                       if v["treatment"] == "fixed_60")
        self.assertFalse(fixed60["equal_completed_work_to_fixed_30"])
        self.assertIsNone(fixed60["descriptive_pareto_nondominated"])

    def test_duplicate_pair_rejected(self):
        data = rows()
        with self.assertRaises(ValueError):
            validate_paired(data + [copy.copy(data[0])])

    def test_different_training_history_rejected(self):
        data = rows()
        data[1]["train_routing_signature"] = "changed"
        with self.assertRaises(AssertionError):
            validate_paired(data)


if __name__ == "__main__":
    unittest.main()
