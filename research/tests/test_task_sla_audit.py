"""Pure tests for independent task-level SLA and response-time accounting."""
import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from statistics import mean
import math

SOURCE=Path(__file__).resolve().parents[1]/"task_sla_audit.py"
tree=ast.parse(SOURCE.read_text(encoding="utf8"))
names=["_minutes","_percentile","analyze_finished_tasks"]
nodes=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
ctx={"math":math,"mean":mean}
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(SOURCE),"exec"),ctx)
analyze_finished_tasks=ctx["analyze_finished_tasks"]

def task(name, start, finish, deadline, arrival=None, duration=None, recorded_met=None):
    arrival=arrival or datetime(2026,1,1,tzinfo=timezone.utc)
    start=arrival+timedelta(minutes=start) if isinstance(start,(int,float)) else start
    finish=arrival+timedelta(minutes=finish) if isinstance(finish,(int,float)) else finish
    deadline=arrival+timedelta(minutes=deadline) if isinstance(deadline,(int,float)) else deadline
    return SimpleNamespace(job_name=name,origin_dc_id=1,dest_dc_id=2,arrival_time=arrival,
                           start_time=start,finish_time=finish,sla_deadline=deadline,
                           duration=duration if duration is not None else (finish-start).total_seconds()/60,
                           sla_met=(finish<=deadline if recorded_met is None else recorded_met))

class TaskSLAContract(unittest.TestCase):
    def setUp(self):
        self.horizon=datetime(2026,1,2,tzinfo=timezone.utc)

    def test_exact_deadline_counts_as_met(self):
        s,rows=analyze_finished_tasks({task("A",5,15,15)},self.horizon)
        self.assertEqual(s["task_audit_violated"],0)
        self.assertEqual(s["task_audit_response_p95_minutes"],15)
        self.assertEqual(rows[0]["waiting_minutes"],5)

    def test_late_task_and_tail_metrics(self):
        a=task("A",10,30,25)
        b=task("B",2,12,15)
        s,rows=analyze_finished_tasks({a,b},self.horizon)
        self.assertEqual(s["task_audit_violated"],1)
        self.assertEqual(s["task_audit_sla_violation_rate"],0.5)
        self.assertEqual(s["task_audit_total_tardiness_minutes"],5)
        self.assertAlmostEqual(s["task_audit_response_mean_minutes"],21)
        self.assertAlmostEqual(s["task_audit_response_p95_minutes"],29.1)

    def test_reported_sla_mismatch_is_rejected(self):
        with self.assertRaisesRegex(AssertionError,"SLA flag"):
            analyze_finished_tasks({task("A",0,10,5,recorded_met=True)},self.horizon)

    def test_execution_duration_mismatch_is_rejected(self):
        with self.assertRaisesRegex(AssertionError,"duration mismatch"):
            analyze_finished_tasks({task("A",0,10,15,duration=8)},self.horizon)

    def test_time_ordering_is_enforced(self):
        with self.assertRaisesRegex(AssertionError,"invalid timeline"):
            analyze_finished_tasks({task("A",20,10,30)},self.horizon)

    def test_empty_completion_cohort(self):
        s,rows=analyze_finished_tasks([],self.horizon)
        self.assertIsNone(s["task_audit_sla_violation_rate"])
        self.assertIsNone(s["task_audit_response_p95_minutes"])
        self.assertEqual(rows,[])

if __name__=="__main__":
    unittest.main()
