"""Independent, data-free contract tests for chronological holdout splits."""
import unittest
from unittest.mock import patch

from research_sci.chronological_eval import timeline_phase, compare


class ChronologicalTests(unittest.TestCase):
    def test_nonoverlapping_phase_boundaries(self):
        phases = [timeline_phase(i, 2, 3, 2, 4) for i in range(11)]
        self.assertEqual(phases, [
            "calibration", "calibration",
            "calibration_drain", "calibration_drain", "calibration_drain",
            "heldout", "heldout",
            "heldout_drain", "heldout_drain", "heldout_drain", "heldout_drain",
        ])

    def test_outside_window_invalid(self):
        for index in (-1, 11):
            with self.assertRaises(ValueError):
                timeline_phase(index, 2, 3, 2, 4)
        with self.assertRaises(ValueError):
            timeline_phase(0, 0, 3, 2, 4)

    @staticmethod
    def example(treatment):
        return {
            "train_window_start": "2023-08-01",
            "train_admissions_end": "2023-08-02",
            "test_window_start": "2023-08-04",
            "test_admissions_end": "2023-08-05",
            "pretest_train_completed": 20,
            "pretest_train_forecast_residuals": 20,
            "pretest_learned_buffer_minutes": 90,
            "train_routing_signature": "same",
            "train_admission_signature": "same",
            "test_admission_signature": "same",
            "test_tasks_admitted": 2,
            "applied_frozen_buffer_minutes": (
                30.0 if treatment == "fixed_30" else 90.0
            ),
        }

    def test_compare_detects_changed_routes(self):
        def fake_one(seed, treatment, **kwargs):
            return self.example(treatment), [
                ("job1", 1),
                ("job2", 1 if treatment == "fixed_30" else 2),
            ]
        with patch("research_sci.chronological_eval.run_one", side_effect=fake_one):
            fixed, calibrated = compare(42)
        self.assertEqual(fixed["paired_dispatch_difference_count"], 1)
        self.assertEqual(calibrated["paired_dispatch_difference_count"], 1)

    def test_compare_rejects_training_contamination(self):
        def fake_one(seed, treatment, **kwargs):
            record = self.example(treatment)
            if treatment == "precalibrated_frozen":
                record["train_routing_signature"] = "different"
            return record, [("job", 1)]
        with patch("research_sci.chronological_eval.run_one", side_effect=fake_one):
            with self.assertRaises(AssertionError):
                compare(42)

    def test_compare_rejects_identical_frozen_margin(self):
        def fake_one(seed, treatment, **kwargs):
            record = self.example(treatment)
            record["applied_frozen_buffer_minutes"] = 30
            return record, [("job", 1)]
        with patch("research_sci.chronological_eval.run_one", side_effect=fake_one):
            with self.assertRaises(AssertionError):
                compare(42)


if __name__ == "__main__":
    unittest.main()
