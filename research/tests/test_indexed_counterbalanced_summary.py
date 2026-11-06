"""Verify order counterbalance summaries retain both positive and negative runs."""
import unittest
from research.indexed_counterbalanced_summary import summarize_counterbalanced


def entry(seed=901):
    return {
        "seed": seed, "tasks_per_policy": 291,
        "exact_task_level_equality": True,
        "orders": {
            "forward": {
                "legacy_p95_ms": 200, "indexed_p95_ms": 190,
                "p95_delta_ms": -10, "per_task_delta_ms": -0.1,
                "projection_delta_seconds": -0.01,
            },
            "reverse": {
                "legacy_p95_ms": 205, "indexed_p95_ms": 209,
                "p95_delta_ms": 4, "per_task_delta_ms": 0.03,
                "projection_delta_seconds": 0.01,
            },
        },
    }


class CounterbalancedSummaryTests(unittest.TestCase):
    def test_preserves_sign_reversal_and_means(self):
        result = summarize_counterbalanced({"jun15_05": [entry()]})
        item = result["scenarios"][0]["seed_results"][0]
        self.assertEqual(item["p95_direction"], "mixed_or_zero")
        self.assertEqual(item["forward"]["p95_delta_ms"], -10)
        self.assertEqual(item["reverse"]["p95_delta_ms"], 4)
        self.assertEqual(item["order_mean"]["p95_delta_ms"], -3)

    def test_consistent_improvement_requires_both_orders(self):
        item = entry()
        item["orders"]["reverse"]["indexed_p95_ms"] = 200
        item["orders"]["reverse"]["p95_delta_ms"] = -5
        item["orders"]["reverse"]["per_task_delta_ms"] = -0.02
        output = summarize_counterbalanced({"test": [item]})
        row = output["scenarios"][0]["seed_results"][0]
        self.assertEqual(row["p95_direction"], "faster_both_orders")
        self.assertEqual(row["per_task_direction"], "faster_both_orders")

    def test_reject_missing_reverse(self):
        item = entry()
        del item["orders"]["reverse"]
        with self.assertRaises(AssertionError):
            summarize_counterbalanced({"test": [item]})

    def test_reject_nonconserved_p95(self):
        item = entry()
        item["orders"]["forward"]["p95_delta_ms"] = -8
        with self.assertRaises(AssertionError):
            summarize_counterbalanced({"test": [item]})

    def test_reject_duplicate_seed(self):
        with self.assertRaises(AssertionError):
            summarize_counterbalanced({"test": [entry(), entry()]})


if __name__ == "__main__":
    unittest.main()
