"""Phase reporting remains consistent with frozen full-horizon forecasts."""
import unittest
from copy import deepcopy

from research.facility_lag_forecast import make_pairs, fit_models, evaluate
from research.facility_lag_phase_audit import phase_audit
from research.tests.test_facility_lag_forecast import r


class PhaseAuditContracts(unittest.TestCase):
    def setUp(self):
        raw=[r(day,seed,dc,t,10+0.5*t) for day in ("06-15","11-12","03-09")
             for seed in (901,1701) for dc in ("A","B") for t in range(17)]
        self.pairs=make_pairs(raw)
        model=fit_models(self.pairs,{"06-15","11-12"})
        self.report={"models":model,"train_metrics":evaluate(
            self.pairs,model,dates=("06-15","11-12")),
            "dev_metrics":[], "test_metrics":evaluate(
                self.pairs,model,dates=("03-09",))}

    def test_complete_phase_partition_and_zero_lag_leakage(self):
        records=phase_audit(self.pairs,self.report,admission_steps=16)
        self.assertEqual(len(records),3*2*2*2)
        for entry in records:
            self.assertEqual(entry["n"],15 if entry["phase"]=="admission" else 1)
            self.assertGreaterEqual(entry["persist_energy"]["p95_abs"],0)

    def test_mismatch_in_original_frozen_metrics_is_fatal(self):
        incorrect=deepcopy(self.report)
        incorrect["test_metrics"][0]["ridge_energy"]["mae"]+=1
        with self.assertRaises(AssertionError):
            phase_audit(self.pairs,incorrect,admission_steps=16)

    def test_missing_or_extra_cohort_rejected(self):
        with self.assertRaises(AssertionError):
            phase_audit(self.pairs[:-1],self.report,admission_steps=16)


if __name__=="__main__":
    unittest.main()
