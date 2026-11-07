"""Ensure risk reports do not pool seeds or misreport denominator."""
import unittest

from research.forecast_risk_stratification import scenario_risk_table


def item(seed, name, slack, actual, remote=False):
    return dict(scenario_start_month=6, scenario_start_day=15,
                seed=seed, policy="queue_nsga2", job_name=name,
                arrival_utc="2026-06-15T00:00:00",
                predicted_slack_minutes=slack,
                residual_actual_minus_prediction_minutes=20 if not actual else 0,
                predicted_sla_met=str(slack >= 0),
                actual_sla_met=str(actual),
                false_safe=str(slack >= 0 and not actual),
                is_remote=str(remote))


class TestRiskStratification(unittest.TestCase):
    def test_separate_seeds_conditional_denominator(self):
        rows=[item(501,"a",5,False,True),
              item(501,"b",70,True),
              item(501,"c",-3,False),
              item(733,"a",10,True)]
        out=scenario_risk_table(rows)
        self.assertEqual(len(out),2)
        x=next(x for x in out if x["seed"]=="501")
        self.assertEqual((x["tasks"],x["predicted_safe"],x["false_safe"]),(3,2,1))
        self.assertEqual(x["false_safe_among_predicted_safe"],.5)
        self.assertEqual(x["by_route"]["remote"]["false_safe"],1)
        self.assertEqual(x["by_predicted_slack"]["predicted_late"]["count"],1)
        self.assertEqual(next(x for x in out if x["seed"]=="733")["false_safe"],0)

    def test_zero_predicted_safe_has_null_rate(self):
        x=scenario_risk_table([item(1,"x",-5,False)])[0]
        self.assertIsNone(x["false_safe_among_predicted_safe"])

    def test_duplicate_rejected(self):
        row=item(1,"x",5,True)
        with self.assertRaises(AssertionError):
            scenario_risk_table([row,row])

    def test_same_name_different_arrival_is_legal(self):
        first=item(1,"same-name",5,True)
        second=dict(first,arrival_utc="2026-06-15T00:15:00")
        self.assertEqual(scenario_risk_table([first,second])[0]["tasks"],2)

    def test_inconsistent_flag_rejected(self):
        row=item(1,"x",5,False)
        row["false_safe"]="False"
        with self.assertRaises(AssertionError):
            scenario_risk_table([row])


if __name__=="__main__":
    unittest.main()
