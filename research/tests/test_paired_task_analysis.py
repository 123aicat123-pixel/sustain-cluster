"""Paired-comparison checks to prevent silently comparing different cohorts."""
import ast
from collections import defaultdict
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "paired_task_analysis.py"
tree = ast.parse(PATH.read_text(encoding="utf8"))
fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
          and node.name == "compare_task_rows")
scope = {"defaultdict": defaultdict}
exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),
             str(PATH), "exec"), scope)
compare = scope["compare_task_rows"]


def row(policy, name, passed=True, dest=1, seed="42", started="T1", finished="T2"):
    return {
        "policy": policy, "seed": seed, "job_name": name,
        "arrival_utc": "T0", "start_utc": started, "finish_utc": finished,
        "deadline_utc": "TD", "duration_minutes": "20",
        "origin_dc_id": "1", "dest_dc_id": str(dest),
        "sla_met": str(passed),
    }


class TestPairedTaskAudit(unittest.TestCase):
    def test_rescued_and_harmed(self):
        data = [
            row("lowest_carbon","a",False),
            row("lowest_carbon","b",True),
            row("sla_feasible_carbon","a",True,dest=2),
            row("sla_feasible_carbon","b",False,dest=2),
        ]
        r=compare(data)
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]["sla_rescued"],1)
        self.assertEqual(r[0]["sla_harmed"],1)
        self.assertEqual(r[0]["destination_changes"],2)

    def test_rejects_mismatched_cohorts(self):
        data=[
            row("lowest_carbon","a"),
            row("sla_feasible_carbon","different"),
        ]
        with self.assertRaisesRegex(AssertionError,"Unequal admission"):
            compare(data)

    def test_rejects_duplicate_tasks(self):
        with self.assertRaisesRegex(AssertionError,"Duplicate task"):
            compare([
                row("lowest_carbon","a"),
                row("lowest_carbon","a"),
            ])

    def test_rejects_changed_deadline(self):
        data=[row("lowest_carbon","a"),row("sla_feasible_carbon","a")]
        data[-1]["deadline_utc"]="CHANGED"
        with self.assertRaisesRegex(AssertionError,"deadline_utc"):
            compare(data)

    def test_detects_identical_task_level_outcomes(self):
        data=[
            row("lowest_carbon","a",False),
            row("edf_sla_carbon","a",False),
        ]
        r=compare(data)[0]
        self.assertEqual(r["sla_rescued"],0)
        self.assertEqual(r["sla_harmed"],0)
        self.assertEqual(r["destination_changes"],0)
        self.assertEqual(r["start_time_changes"],0)
        self.assertEqual(r["finish_time_changes"],0)


if __name__ == "__main__":
    unittest.main()
