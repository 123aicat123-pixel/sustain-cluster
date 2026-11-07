"""Independent matched-route audit: no hidden second changed destination."""
import unittest

from research.single_route_intervention_audit import audit_route_probe


def task(policy, dest, name="job", sla="True"):
    return {"policy":policy,"seed":1,"arrival_utc":"2023-06-15T05:00:00+00:00",
            "job_name":name,"origin_dc_id":1,"dest_dc_id":dest,
            "duration_minutes":"30", "deadline_utc":"2023-06-15T06:00:00+00:00",
            "start_utc":"2023-06-15T05:00:00+00:00",
            "finish_utc":"2023-06-15T05:30:00+00:00","sla_met":sla}


def cell(policy):
    return {"policy":policy,"seed":1,"dc_name":"DC1","step_index":0,
            "energy_kwh":7.0,"effective_ci_g_per_kwh":200.0,
            "carbon_kg":1.4,"it_power_kw":20.0,
            "hvac_power_kw":8.0,"total_dc_power_kw":28.0}


def run(policy,selected):
    arm=policy.removeprefix("probe_")
    return {"seed":1,"policy":policy,"fully_drained":True,
            "fallback_assignments":0,"tasks_finished":2,"tasks_dispatched":2,
            "reported_total_carbon_kg":1.4,"facility_carbon_kg":1.4,
            "transmission_carbon_kg":0,"reported_total_cost_usd":4.0,
            "sla_violated":0,
            "probe_intervention":{
                "arm":arm,"task_name":"job","task_index":0,
                "control_dc_id":1,"selected_dc_id":selected,
                "original_action":1,"chosen_action":selected,
                "observed_selected_ci":100.0 if selected==2 else 300.0 if selected==3 else 250.0,
                "original_cpu_cores":2,"duration_minutes":30,
            }}


class SingleRouteAuditTests(unittest.TestCase):
    def setUp(self):
        self.runs=[run("probe_control",1),run("probe_low_ci",2),
                   run("probe_high_ci",3)]
        self.tasks=[]
        for name,dc in (("probe_control",1),("probe_low_ci",2),
                        ("probe_high_ci",3)):
            self.tasks.append(task(name,dc))
            self.tasks.append(task(name,1,name="unchanged"))
        self.cells=[cell(r["policy"]) for r in self.runs]

    def test_one_changed_task_reconciles(self):
        report=audit_route_probe(self.runs,self.tasks,self.cells)
        self.assertEqual(len(report),2)
        for record in report:
            self.assertEqual(record["changed_task_routes"],1)
            self.assertEqual(record["measured_facility_carbon_delta_kg"],0)
            self.assertEqual(record["sla_harmed"],0)
            self.assertEqual(record["measured_total_carbon_delta_kg"],0)
        self.assertLess(report[0]["fixed_6w_core_carbon_proxy_delta_kg"],0)
        self.assertGreater(report[1]["fixed_6w_core_carbon_proxy_delta_kg"],0)

    def test_hidden_second_route_is_fatal(self):
        changed=[dict(t) for t in self.tasks]
        for row in changed:
            if row["policy"]=="probe_low_ci" and row["job_name"]=="unchanged":
                row["dest_dc_id"]=2
        with self.assertRaises(AssertionError):
            audit_route_probe(self.runs,changed,self.cells)

    def test_inconsistent_selected_route_is_fatal(self):
        bad=[dict(r) for r in self.runs]
        bad[1]=dict(bad[1],probe_intervention=dict(
            bad[1]["probe_intervention"],selected_dc_id=3))
        with self.assertRaises(AssertionError):
            audit_route_probe(bad,self.tasks,self.cells)

    def test_missing_cell_is_fatal(self):
        with self.assertRaises(AssertionError):
            audit_route_probe(self.runs,self.tasks,self.cells[:-1])


if __name__ == "__main__":
    unittest.main()
