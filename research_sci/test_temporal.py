"""Deterministic tests of per-task temporal choices without simulator deps."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research_sci.temporal import TemporalPolicy


class FakeCenter:
    def __init__(self, dc_id, carbon):
        self.dc_id = dc_id
        self.location = f"region-{dc_id}"
        self.carbon = carbon

    def get_current_carbon_intensity(self, norm=False):
        return self.carbon

    def can_schedule(self, task):
        return True


class TestTemporalPolicy(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.dc = {"A": FakeCenter(1, 400)}
        self.cluster = SimpleNamespace(
            cloud_provider="aws", get_dc_location=lambda dc_id: "origin")
        self.task = SimpleNamespace(
            origin_dc_id=1, duration=15, sla_deadline=self.now + timedelta(hours=4),
            bandwidth_gb=0,
        )
        self.delay = lambda *args: 0.0

    def choose(self, policy, time=None):
        return policy.choose(self.task, self.dc, time or self.now, self.cluster)

    def test_wait_once_then_dispatch(self):
        p = TemporalPolicy("slack_wait_once", delay_fn=self.delay)
        self.assertEqual(self.choose(p), (0, False))
        self.assertEqual(self.choose(p, self.now + timedelta(minutes=15)), (1, False))
        self.assertEqual(p.deferral_count[self.task], 1)

    def test_tight_deadline_prevents_deferral(self):
        self.task.sla_deadline = self.now + timedelta(minutes=30)
        p = TemporalPolicy("slack_wait_once", delay_fn=self.delay)
        self.assertEqual(self.choose(p), (1, False))

    def test_history_only_past_observations(self):
        p = TemporalPolicy("causal_carbon_wait", delay_fn=self.delay, threshold_pct=5)
        for k, carbon in enumerate((100, 100, 100, 400)):
            self.dc["A"].carbon = carbon
            result = self.choose(p, self.now + timedelta(minutes=15*k))
        self.assertEqual(result, (0, False))
        self.assertEqual(len(p.history), 4)

    def test_tight_deadline_overrides_history(self):
        p = TemporalPolicy("causal_carbon_wait", delay_fn=self.delay)
        for k in range(3):
            self.dc["A"].carbon = 100
            self.choose(p, self.now + timedelta(minutes=15*k))
        self.dc["A"].carbon = 400
        self.task.sla_deadline = self.now + timedelta(minutes=60)
        self.assertEqual(self.choose(p, self.now + timedelta(minutes=45)), (1, False))

    def test_wait_budget(self):
        p = TemporalPolicy("causal_carbon_wait", delay_fn=self.delay, max_waits=1)
        for k, carbon in enumerate((100, 100, 100, 400, 400)):
            self.dc["A"].carbon = carbon
            result = self.choose(p, self.now + timedelta(minutes=15*k))
        self.assertEqual(result, (1, False))
        self.assertEqual(p.deferral_count[self.task], 1)

    def test_no_forecast_in_constructor(self):
        with self.assertRaises(ValueError):
            TemporalPolicy("causal_carbon_wait", delay_fn=self.delay, window=1)


if __name__ == "__main__":
    unittest.main()
