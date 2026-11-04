"""Regression for heterogeneous queue-aware/full baseline CSV columns."""
import csv
import io
import unittest

from research.csv_export_schema import union_csv_fieldnames


class TestUnifiedCsvColumns(unittest.TestCase):
    def test_preserves_late_forecast_columns_and_all_rows(self):
        rows = [
            {"policy": "sla_feasible_carbon", "seed": 501, "sla_violated": 1},
            {"policy": "queue_nsga2", "seed": 501, "sla_violated": 0,
             "forecast_mae_minutes": 15.2, "forecast_false_safe_count": 3},
        ]
        headers = union_csv_fieldnames(rows)
        self.assertEqual(
            headers,
            ["policy", "seed", "sla_violated",
             "forecast_mae_minutes", "forecast_false_safe_count"],
        )
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        output.seek(0)
        parsed = list(csv.DictReader(output))
        self.assertEqual(parsed[0]["forecast_mae_minutes"], "")
        self.assertEqual(parsed[1]["forecast_mae_minutes"], "15.2")
        self.assertEqual(parsed[1]["forecast_false_safe_count"], "3")

    def test_no_rows_is_error(self):
        with self.assertRaises(ValueError):
            union_csv_fieldnames([])


if __name__ == "__main__":
    unittest.main()
