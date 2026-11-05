"""Contract tests for descriptive latency outputs."""
import unittest

from research.planner_latency import summarize_dispatch_latency


class PlannerLatencyTests(unittest.TestCase):
    def test_empty(self):
        row = summarize_dispatch_latency([], [])
        self.assertEqual(row["planner_dispatch_calls"], 0)
        self.assertIsNone(row["planner_dispatch_p95_ms"])

    def test_nearest_rank_and_weighting(self):
        row = summarize_dispatch_latency([0.001, 0.003, 0.002, 0.005], [1, 2, 1, 6])
        self.assertEqual(row["planner_dispatch_p50_ms"], 2.0)
        self.assertEqual(row["planner_dispatch_p95_ms"], 5.0)
        self.assertEqual(row["planner_dispatched_tasks"], 10)
        self.assertAlmostEqual(row["planner_dispatch_ms_per_task"], 1.1)
        self.assertAlmostEqual(row["planner_dispatch_mean_ms"], 2.75)

    def test_invalid(self):
        for seconds, sizes in [([0.1], []), ([-0.1], [1]),
                               ([float("nan")], [1]), ([0.1], [0])]:
            with self.subTest(seconds=seconds, sizes=sizes):
                with self.assertRaises(ValueError):
                    summarize_dispatch_latency(seconds, sizes)


if __name__ == "__main__":
    unittest.main()
