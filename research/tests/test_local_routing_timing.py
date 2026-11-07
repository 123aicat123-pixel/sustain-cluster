"""Execute the real TaskSchedulingEnv.step method with tiny mocked cluster.

Covers the local zero-transfer fast path and the remote transmission queue.
The test exercises the METHOD BODY from upstream via AST, not a reimplementation.
"""
import ast
from collections import deque
import unittest
from pathlib import Path
from types import SimpleNamespace
import pandas as pd

SOURCE=Path(__file__).resolve().parents[2]/"envs/task_scheduling_env.py"


def method():
    ast_tree=ast.parse(SOURCE.read_text(encoding="utf8"))
    cls=next(n for n in ast_tree.body if isinstance(n,ast.ClassDef) and n.name=="TaskSchedulingEnv")
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="step")
    namespace={"pd":pd,"get_transmission_delay":lambda *args:30.0}
    mod=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]))
    exec(compile(mod,str(SOURCE),"exec"),namespace)
    return namespace["step"]


class LocalRoutingTimingTest(unittest.TestCase):
    def setUp(self):
        self.step=method()
        self.now=pd.Timestamp("2023-08-01T05:00:00Z")

    def make_env(self, single=False):
        dc1=SimpleNamespace(dc_id=1,location="us-east-1",pending_tasks=deque())
        dc2=SimpleNamespace(dc_id=2,location="us-west-1",pending_tasks=deque())
        datacenters={"DC1":dc1,"DC2":dc2}
        cm=SimpleNamespace(
            strategy="manual_rl",datacenters=datacenters,
            cloud_provider="aws",
            get_dc_location=lambda dcid: "us-east-1" if dcid==1 else "us-west-1",
            step=lambda time,logger=None: {
                "datacenter_infos": {},
                "transmission_cost_total_usd":0.0,
            },
        )
        task=SimpleNamespace(
            origin_dc_id=1,dest_dc_id=None,dest_dc=None,
            sla_deadline=self.now+pd.Timedelta(hours=4),
            job_name="example",bandwidth_gb=1.0,
        )
        env=SimpleNamespace(
            single_action_mode=single,disable_defer_action=False,
            current_time=self.now,time_step=pd.Timedelta(minutes=15),
            end_time=self.now+pd.Timedelta(hours=6),
            current_tasks=[task],in_transit_tasks=[],deferred_tasks=[],
            logger=None,cluster_manager=cm,global_step=0,
            writer=None,reward_fn=None,
            _load_new_tasks=lambda:None,
            _get_obs=lambda:[],
        )
        return env, task, dc1, dc2

    def test_local_placement_enters_queue_this_step_per_task(self):
        env,task,dc1,dc2=self.make_env()
        self.step(env,[1])
        self.assertEqual(list(dc1.pending_tasks),[task])
        self.assertEqual(env.in_transit_tasks,[])
        self.assertEqual(task.dest_dc_id,1)

    def test_local_placement_enters_queue_this_step_single_action(self):
        env,task,dc1,dc2=self.make_env(single=True)
        self.step(env,1)
        self.assertEqual(list(dc1.pending_tasks),[task])
        self.assertEqual(env.in_transit_tasks,[])

    def test_remote_placement_remains_in_transit_until_later_step(self):
        env,task,dc1,dc2=self.make_env()
        self.step(env,[2])
        self.assertEqual(list(dc2.pending_tasks),[])
        self.assertEqual(len(env.in_transit_tasks),1)
        self.assertEqual(task.dest_dc_id,2)
        self.assertEqual(env.in_transit_tasks[0][0],self.now+pd.Timedelta(seconds=30))
        env.current_tasks=[]
        self.step(env,[])
        self.assertEqual(list(dc2.pending_tasks),[task])
        self.assertEqual(env.in_transit_tasks,[])

    def test_remote_placement_single_action(self):
        env,task,dc1,dc2=self.make_env(single=True)
        self.step(env,2)
        self.assertEqual(len(env.in_transit_tasks),1)
        self.assertEqual(list(dc2.pending_tasks),[])


if __name__=="__main__":
    unittest.main()
