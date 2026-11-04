import unittest
from unittest.mock import patch
from research_sci.nested_validation import plan_windows,select_validation,audit_pair
from research_sci.risk_frontier import TREATMENTS
from research_sci.test_risk_frontier import example

class NestedTests(unittest.TestCase):
    def test_nonoverlapping(self):
        p=plan_windows(16,128,16,128,16,96)
        self.assertEqual(p["val_begin"],144)
        self.assertEqual(p["val_end"],160)
        self.assertEqual(p["test_begin"],288)
        self.assertEqual(p["test_gap"],272)
        with self.assertRaises(ValueError):
            plan_windows(16,128,16,128,16,400)

    def test_selection_only_validation(self):
        rows=[example(seed,treatment) for seed in (1,42) for treatment in TREATMENTS]
        selected,diag=select_validation(rows)
        self.assertEqual(selected,"fixed_30")
        self.assertEqual(len(diag),4)
        for r in rows:
            if r["treatment"]=="fixed_60":
                r["test_total_carbon_kg"]=50
        selected,_=select_validation(rows)
        self.assertEqual(selected,"fixed_60")

    def test_validation_rejects_equal_count_but_different_tasks(self):
        rows=[example(seed,treatment) for seed in (1,42)
              for treatment in TREATMENTS]
        for record in rows:
            if record["treatment"] == "fixed_60":
                record["test_total_carbon_kg"] = 1
                record["test_finished_work_signature"] = "different"
        selected,_=select_validation(rows)
        self.assertEqual(selected,"fixed_30")

    def test_audit_rejects_mismatch(self):
        base=example(1,"fixed_30")
        chosen=example(1,"fixed_60")
        for x in (base,chosen):
            x["gap_steps"]=272
            x["pretest_training_sample_is_disjoint"]=True
        audit_pair(base,chosen,"fixed_60",272)
        chosen["test_admission_signature"]="different"
        with self.assertRaises(AssertionError):
            audit_pair(base,chosen,"fixed_60",272)

if __name__=="__main__":
    unittest.main()
