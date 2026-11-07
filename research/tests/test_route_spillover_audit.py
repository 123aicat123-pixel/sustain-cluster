"""Test route-changed vs unchanged-route SLA decomposition."""
import unittest
from research.route_spillover_audit import audit_route_spillover

BASE="queue_nsga2_indexed_transit"
ALT="queue_nsga2_lagged_pue"


def row(policy, seed, name, dest, start, met):
    return {
        "policy": policy, "seed": seed,
        "arrival_utc": "2020-01-20T00:00:00Z",
        "job_name": name, "duration_minutes": "15",
        "deadline_utc": "2020-01-20T01:00:00Z",
        "origin_dc_id": "1", "dest_dc_id": dest,
        "start_utc": start,
        "finish_utc": "2020-01-20T01:15:00Z" if not met else "2020-01-20T00:30:00Z",
        "sla_met": str(met),
    }


def rows():
    out=[]
    for seed in (901,1701):
        out.extend([
            row(BASE,seed,"A","1","00:00",True),
            row(BASE,seed,"B","2","00:00",True),
            row(ALT,seed,"A","3","00:15",False),
            row(ALT,seed,"B","2","00:15",False),
        ])
    return out


class RouteSpilloverTests(unittest.TestCase):
    def test_separates_rerouted_and_queue_spillovers(self):
        result = audit_route_spillover(rows(),BASE,[ALT])
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]["route_change_partitions"]["route_changed"]["sla_harmed"],1)
        self.assertEqual(result[0]["route_change_partitions"]["route_unchanged"]["sla_harmed"],1)
        self.assertEqual(result[0]["sla_miss_delta"],2)

    def test_rejects_missing_cohort(self):
        data=rows()
        data=[r for r in data if not (r["seed"]==1701 and r["job_name"]=="B" and r["policy"]==ALT)]
        with self.assertRaises(AssertionError):
            audit_route_spillover(data,BASE,[ALT])

    def test_rejects_task_mutation(self):
        data=rows()
        data[2]["deadline_utc"]="2020-01-20T03:00:00Z"
        with self.assertRaises(AssertionError):
            audit_route_spillover(data,BASE,[ALT])

    def test_rejects_duplicate_task(self):
        data=rows()
        data.append(dict(data[0]))
        with self.assertRaises(AssertionError):
            audit_route_spillover(data,BASE,[ALT])

    def test_rejects_malformed_sla(self):
        data=rows()
        data[2]["sla_met"]="unknown"
        with self.assertRaises(ValueError):
            audit_route_spillover(data,BASE,[ALT])


if __name__ == "__main__":
    unittest.main()
