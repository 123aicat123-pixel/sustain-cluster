"""Independent and deterministic tests for proposed research accounting and SLA baseline."""
import ast
import math
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def load_top_level(path, name, namespace=None):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
    code = compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(ROOT / path), "exec")
    ctx = dict(namespace or {})
    exec(code, ctx)
    return ctx[name]


audit_lifecycle = load_top_level("research/lifecycle_audit.py", "audit_lifecycle")
SLAPolicy = load_top_level(
    "research/sla_carbon_policy.py", "SLAFeasibleCarbonPolicy",
    {"math": math, "timedelta": timedelta},
)


def make_dc(dc_id, carbon, price, location, fits=True):
    return SimpleNamespace(
        dc_id=dc_id, location=location,
        can_schedule=lambda task: fits,
        get_current_carbon_intensity=lambda norm=False: carbon,
        price_manager=SimpleNamespace(get_current_price=lambda: price),
    )


class TestLifecycleAudit(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.c, self.d = [object() for _ in range(4)]

    def test_exact_conservation(self):
        result = audit_lifecycle(
            {self.a, self.b, self.c, self.d},
            [self.a], [self.b], [self.c], [self.d]
        )
        self.assertEqual(result, {
            "finished": 1, "pending": 1, "running": 1,
            "in_transit": 1, "dispatched": 4, "unfinished": 3,
        })

    def test_missing_task_rejected(self):
        with self.assertRaisesRegex(AssertionError, "missing"):
            audit_lifecycle({self.a, self.b}, [self.a], [], [], [])

    def test_cross_state_duplicate_rejected(self):
        with self.assertRaisesRegex(AssertionError, "appears in"):
            audit_lifecycle({self.a}, [self.a], [self.a], [], [])

    def test_duplicate_in_same_queue_rejected(self):
        with self.assertRaisesRegex(AssertionError, "Repeated"):
            audit_lifecycle({self.a}, [], [self.a, self.a], [], [])

    def test_undispatched_task_rejected(self):
        with self.assertRaisesRegex(AssertionError, "Unknown"):
            audit_lifecycle({self.a}, [self.a], [], [], [self.b])


class TestSLAFeasibleCarbonPolicy(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.dcs = {
            "DC10": make_dc(10, carbon=100, price=70, location="far"),
            "DC2": make_dc(2, carbon=400, price=30, location="near"),
        }
        self.cm = SimpleNamespace(
            cloud_provider="aws",
            get_dc_location=lambda origin_id: "origin",
        )

    def task(self, deadline_mins=40, duration=10):
        return SimpleNamespace(
            origin_dc_id=2, bandwidth_gb=1.0,
            duration=duration,
            sla_deadline=self.now + timedelta(minutes=deadline_mins),
        )

    def test_sla_avoids_clean_but_too_late_dc(self):
        policy = SLAPolicy(delay_fn=lambda a,b,c,d: 4000 if b == "far" else 30)
        policy.set_context(self.now, self.cm)
        self.assertEqual(policy(self.task(), self.dcs), 2)

    def test_cleanest_selected_when_both_feasible(self):
        policy = SLAPolicy(delay_fn=lambda a,b,c,d: 30)
        policy.set_context(self.now, self.cm)
        self.assertEqual(policy(self.task(), self.dcs), 10)

    def test_when_none_meet_deadline_pick_earliest(self):
        policy = SLAPolicy(delay_fn=lambda a,b,c,d: 4000 if b == "far" else 30)
        policy.set_context(self.now, self.cm)
        self.assertEqual(policy(self.task(deadline_mins=5), self.dcs), 2)

    def test_local_zero_transfer_meets_tight_deadline(self):
        policy = SLAPolicy(delay_fn=lambda a,b,c,d: 30)
        policy.set_context(self.now, self.cm)
        # Local: immediate 10 minute execution. Remote: >=15 minute transfer
        # grid delay + 10 minute execution, too late for 10 minute deadline.
        self.assertEqual(policy(self.task(deadline_mins=10, duration=10),self.dcs),2)

    def test_excludes_currently_unschedulable_dc(self):
        self.dcs["DC10"].can_schedule=lambda task: False
        policy = SLAPolicy(delay_fn=lambda a,b,c,d: 30)
        policy.set_context(self.now, self.cm)
        self.assertEqual(policy(self.task(), self.dcs), 2)

    def test_no_candidates_returns_none(self):
        self.dcs["DC10"].can_schedule=lambda task: False
        self.dcs["DC2"].can_schedule=lambda task: False
        policy = SLAPolicy(delay_fn=lambda a,b,c,d: 30)
        policy.set_context(self.now, self.cm)
        self.assertIsNone(policy(self.task(), self.dcs))

    def test_context_required(self):
        with self.assertRaises(RuntimeError):
            SLAPolicy(delay_fn=lambda a,b,c,d: 0)(self.task(), self.dcs)

    def test_bad_delay_rejected(self):
        policy=SLAPolicy(delay_fn=lambda a,b,c,d: -1)
        policy.set_context(self.now, self.cm)
        with self.assertRaises(ValueError):
            policy(self.task(), self.dcs)


if __name__ == "__main__":
    unittest.main()
