"""Dataset-free tests of exploratory paired seed summarization."""
import unittest

from research_sci.summarize import summarize


def sample(seed, policy, carbon, done=10, total=12):
    return {
        "seed": seed,
        "policy": policy,
        "tasks_dispatched": total,
        "tasks_finished": done,
        "unfinished_at_horizon": total - done,
        "unfinished_overdue": 1,
        "total_reported_carbon_kg": float(carbon),
    }


class SummaryTests(unittest.TestCase):
    def test_paired_relative_change(self):
        rows = [
            sample(1, "round_robin", 100), sample(1, "lowest_carbon", 90),
            sample(2, "round_robin", 200), sample(2, "lowest_carbon", 220),
        ]
        result = summarize(rows)
        self.assertAlmostEqual(
            result["policies"]["lowest_carbon"]["mean_paired_carbon_delta_pct"], 0.0
        )
        self.assertEqual(result["seeds"], [1, 2])

    def test_unequal_completion_flag(self):
        rows = [sample(1, "round_robin", 100), sample(1, "lowest_carbon", 80, done=9)]
        result = summarize(rows)
        self.assertTrue(
            result["policies"]["lowest_carbon"]["comparison_not_fair_if_unequal_completed"]
        )

    def test_mismatched_arrivals_rejected(self):
        rows = [sample(1, "round_robin", 100), sample(1, "lowest_carbon", 80, total=13)]
        with self.assertRaises(ValueError):
            summarize(rows)

    def test_missing_pair_rejected(self):
        rows = [
            sample(1, "round_robin", 100), sample(1, "lowest_carbon", 90),
            sample(2, "round_robin", 100),
        ]
        with self.assertRaises(ValueError):
            summarize(rows)

    def test_duplicate_pair_rejected(self):
        rows = [sample(1, "round_robin", 100), sample(1, "round_robin", 100)]
        with self.assertRaises(ValueError):
            summarize(rows)


if __name__ == "__main__":
    unittest.main()
