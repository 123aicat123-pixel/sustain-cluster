"""Tests for retrospective, non-actionable SLA forecast error decomposition."""
import unittest
from research.sla_miss_diagnostics import analyze


def r(policy, slack, delay, *, remote=False):
    pred = slack >= 0
    actual = (slack - delay) >= 0
    return {
        "policy": policy, "predicted_slack_minutes": str(slack),
        "residual_actual_minus_prediction_minutes": str(delay),
        "predicted_sla_met": str(pred),
        "actual_sla_met": str(actual),
        "false_safe": str(pred and not actual),
        "is_remote": str(remote),
    }


class TestSlaMissDiagnostics(unittest.TestCase):
    def test_slack_and_transfer_grouping(self):
        rows=[
            r("q", 5, 15, remote=True),   # false safe in 0-15m band
            r("q", 20, 30),                # false safe in 15-30m
            r("q", 100, 0),                # safe in 60m+ band
            r("q", -5, -10),               # predicted late but actual safe
        ]
        x=analyze(rows)
        report=x["policy_results"]["q"]["grouped"]
        self.assertEqual(report["all"]["count"],4)
        self.assertEqual(report["all"]["false_safe"],2)
        self.assertEqual(report["all"]["false_alarm"],1)
        self.assertEqual(report["remote"]["false_safe"],1)
        self.assertEqual(report["pred_safe_0_to_15m"]["count"],1)
        self.assertEqual(report["pred_safe_15_to_30m"]["count"],1)
        self.assertEqual(report["predicted_late"]["count"],1)
        buffers=x["policy_results"]["q"]["retrospective_buffer_classification_only"]
        self.assertEqual(buffers[0]["actual_misses_unchanged"],2)
        self.assertEqual(buffers[0]["false_safe"],2)
        self.assertEqual(buffers[1]["false_safe"],1)
        self.assertEqual(buffers[1]["false_alarm"],1)

    def test_classification_does_not_change_actual_misses(self):
        rows=[r("q",15,30),r("q",80,15),r("q",0,0)]
        sweeps=analyze(rows)["policy_results"]["q"]["retrospective_buffer_classification_only"]
        self.assertEqual({s["actual_misses_unchanged"] for s in sweeps},{1})

    def test_rejects_inconsistent_false_safe(self):
        row=r("q",10,20)
        row["false_safe"]="False"
        with self.assertRaises(AssertionError):
            analyze([row])

    def test_rejects_nonfinite_values(self):
        row=r("q",10,20)
        row["predicted_slack_minutes"]="nan"
        with self.assertRaises(ValueError):
            analyze([row])

    def test_empty(self):
        self.assertEqual(analyze([])["policy_results"],{})


if __name__=="__main__":
    unittest.main()
