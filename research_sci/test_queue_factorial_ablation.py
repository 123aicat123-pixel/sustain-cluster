"""Contract tests for queue-order factorial, including work-matching gate."""
import unittest
from research_sci.queue_factorial_ablation import CONFIGS,compare_factorial


def row(execution,forecast,carbon=100,misses=4,finished="same"):
    return {
        "queue_discipline":execution,
        "forecast_queue_discipline":forecast,
        "seed":1,"capacity_scale":.1,"window_index":0,
        "test_window_start":"start","test_admissions_end":"end",
        "train_window_start":"train","train_admissions_end":"train_end",
        "test_tasks_admitted":10,"test_admission_signature":"same",
        "train_routing_signature":"same",
        "train_admission_signature":"same",
        "pretest_train_completed":10,"pretest_learned_buffer_minutes":50,
        "applied_frozen_buffer_minutes":30,
        "test_tasks_finished":10,"test_unfinished":0,
        "test_unfinished_overdue":0,
        "test_deadline_failures_including_overdue":misses,
        "test_finished_work_signature":finished,
        "test_total_carbon_kg":carbon,
        "test_routing_signature":"some",
    }


class FactorialTests(unittest.TestCase):
    def test_all_2x2_and_separate_effects(self):
        group=[row(e,p,carbon=100+i*2,misses=4+i)
               for i,(e,p) in enumerate(CONFIGS)]
        report=compare_factorial(group)
        self.assertEqual(len(report),4)
        self.assertEqual(report[0]["sla_delta_to_fifo_fifo"],0)
        self.assertEqual(report[1]["sla_delta_to_fifo_fifo"],1)
        self.assertEqual(report[2]["sla_delta_to_fifo_fifo"],2)
        self.assertEqual(report[3]["sla_delta_to_fifo_fifo"],3)

    def test_different_finished_jobs_exclude_carbon_delta(self):
        group=[row(e,p,finished=("other" if (e,p)==("edf","edf") else "same"))
               for e,p in CONFIGS]
        report=compare_factorial(group)
        self.assertIsNone(report[-1]["carbon_delta_pct_if_identical_work"])
        self.assertTrue(report[1]["identical_completed_work"])

    def test_missing_combinations_are_rejected(self):
        with self.assertRaises(AssertionError):
            compare_factorial([row("fifo","fifo"),row("edf","edf")])

    def test_training_history_and_admission_order_must_match(self):
        group=[row(e,p) for e,p in CONFIGS]
        group[1]["train_routing_signature"]="changed"
        with self.assertRaises(AssertionError):
            compare_factorial(group)


if __name__=="__main__":
    unittest.main()
