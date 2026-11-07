"""Prospective validation must never rank unmatched or censored outcomes."""
import unittest

from research.prospective_transit_audit import audit_scenario


def run(seed, policy, *, finished=2, unfinished=0, fallback=0, misses=0):
    return dict(seed=seed, policy=policy,
                scenario_start_month=2, scenario_start_day=12,
                cpu_capacity_scale=0.05, lifecycle_conserved=True,
                task_audit_completed=finished, tasks_finished=finished,
                tasks_dispatched=2, sla_met=finished-misses,
                sla_violated=misses, fully_drained=unfinished==0,
                unfinished_dispatched=unfinished, fallback_assignments=fallback,
                reported_total_cost_usd=5, reported_total_carbon_kg=10,
                forecast_count=finished, forecast_actual_sla_misses=misses)


def tasks(seed, policy):
    return [dict(seed=str(seed), policy=policy,
                 arrival_utc=f"2020-02-12T00:{i:02d}:00",
                 job_name=f"task{i}", duration_minutes="20",
                 deadline_utc=f"2020-02-12T01:{i:02d}:00",
                 origin_dc_id="1", dest_dc_id="1",
                 start_utc=f"2020-02-12T00:{i:02d}:00",
                 finish_utc=f"2020-02-12T00:{i+20:02d}:00",
                 sla_met="True") for i in range(2)]


POLICIES=("queue_nsga2_no_queue","queue_nsga2","queue_nsga2_with_transit")


class TestProspectiveAudit(unittest.TestCase):
    def test_paired_complete_and_valid(self):
        rows=[run(901,p) for p in POLICIES]
        records=[t for p in POLICIES for t in tasks(901,p)]
        result=audit_scenario(rows,records,month=2,day=12,cpu_scale=.05,
                              seeds=(901,),policies=POLICIES)
        self.assertTrue(result[0]["eligible"])
        self.assertEqual(len(result[0]["paired_outcomes"]),2)
        self.assertTrue(all(x["sla_misses_delta"]==0
                            for x in result[0]["paired_outcomes"]))

    def test_partial_drain_is_censored(self):
        rows=[run(901,p) for p in POLICIES]
        rows[0]["unfinished_dispatched"]=1
        rows[0]["fully_drained"]=False
        result=audit_scenario(rows,[],month=2,day=12,cpu_scale=.05,
                              seeds=(901,),policies=POLICIES)[0]
        self.assertFalse(result["eligible"])
        self.assertNotIn("paired_outcomes",result)

    def test_duplicate_run_is_error(self):
        rows=[run(901,p) for p in POLICIES]
        with self.assertRaises(AssertionError):
            audit_scenario(rows+rows[:1],[],month=2,day=12,
                           cpu_scale=.05,seeds=(901,),policies=POLICIES)

    def test_calendar_mismatch_is_error(self):
        rows=[run(901,p) for p in POLICIES]
        rows[0]["scenario_start_month"]=4
        with self.assertRaises(AssertionError):
            audit_scenario(rows,[],month=2,day=12,
                           cpu_scale=.05,seeds=(901,),policies=POLICIES)


if __name__=="__main__":
    unittest.main()
