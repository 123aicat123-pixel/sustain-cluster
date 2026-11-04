"""Deterministic tests for queue completion prediction and causal risk controls."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from research_sci.queue_risk import QueueRiskCarbonPolicy, predict_finish


class IdentityTask:
    def __init__(self, name, duration=15, cpu=1, gpu=0, mem=0, deadline=None):
        self.job_name = name
        self.duration = float(duration)
        self.cores_req = float(cpu)
        self.gpu_req = float(gpu)
        self.mem_req = float(mem)
        self.bandwidth_gb = 0
        self.origin_dc_id = 1
        self.sla_deadline = deadline


class FakeDC:
    def __init__(self, dc_id, carbon=300, cores=2):
        self.dc_id = dc_id
        self.location = f"dc-{dc_id}"
        self.carbon = carbon
        self.available_cores = float(cores)
        self.available_gpus = 1.0
        self.available_mem = 100.0
        self.total_cores = 2.0
        self.total_gpus = 1.0
        self.total_mem = 100.0
        self.running_tasks = []
        self.pending_tasks = []

    def can_schedule(self, task):
        return (self.available_cores >= task.cores_req
                and self.available_gpus >= task.gpu_req
                and self.available_mem >= task.mem_req)

    def get_current_carbon_intensity(self, norm=False):
        return self.carbon


class QueueEstimatorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.dc = FakeDC(1)
        self.task = IdentityTask("target", deadline=self.now + timedelta(hours=2))
        self.cluster = SimpleNamespace(
            cloud_provider="aws", get_dc_location=lambda dc_id: f"dc-{dc_id}")

    def test_empty_queue_arrives_next_tick(self):
        self.assertEqual(
            predict_finish(self.task, self.dc, self.now, 1),
            self.now + timedelta(minutes=30),
        )

    def test_running_job_release_is_used(self):
        self.dc.available_cores = 0
        running = IdentityTask("running", cpu=2)
        running.finish_time = self.now + timedelta(minutes=30)
        self.dc.running_tasks = [running]
        self.assertEqual(
            predict_finish(self.task, self.dc, self.now, 1),
            self.now + timedelta(minutes=45),
        )

    def test_pending_queue_is_replayed(self):
        self.dc.available_cores = 0
        running = IdentityTask("running", cpu=2)
        running.finish_time = self.now + timedelta(minutes=30)
        self.dc.running_tasks = [running]
        self.dc.pending_tasks = [IdentityTask("pending", cpu=2, duration=30)]
        self.assertEqual(
            predict_finish(self.task, self.dc, self.now, 1),
            self.now + timedelta(minutes=75),
        )

    def test_excess_demand_returns_none(self):
        self.task.cores_req = 3
        self.assertIsNone(predict_finish(self.task, self.dc, self.now, 1, max_ticks=4))

    def test_in_transit_reservation_delays_future_arrival(self):
        prior = IdentityTask("already-in-transit", duration=60, cpu=2)
        arrival = self.now + timedelta(minutes=15)
        self.assertEqual(
            predict_finish(self.task, self.dc, self.now, 1,
                           known_arrivals=[(arrival, prior)]),
            self.now + timedelta(minutes=90),
        )

    def test_no_hidden_arrivals_and_no_double_reservation(self):
        prior = IdentityTask("previous-batch", duration=30, cpu=2)
        arrival = self.now + timedelta(minutes=15)
        prediction = predict_finish(
            self.task, self.dc, self.now, 1,
            known_arrivals=[(arrival, prior)])
        self.assertEqual(prediction, self.now + timedelta(minutes=60))
        with self.assertRaises(AssertionError):
            predict_finish(self.task, self.dc, self.now, 1,
                           known_arrivals=[(arrival, self.task)])

    def test_reject_invalid_horizon(self):
        with self.assertRaises(ValueError):
            predict_finish(self.task, self.dc, self.now, 0)

    def test_queue_baseline_prefers_feasible_sla(self):
        dirty = FakeDC(1, carbon=600, cores=2)
        green = FakeDC(2, carbon=100, cores=0)
        runner = IdentityTask("busy", cpu=2)
        runner.finish_time = self.now + timedelta(hours=4)
        green.running_tasks = [runner]
        dcs = {"dirty": dirty, "green": green}
        policy = QueueRiskCarbonPolicy("queue_risk_carbon", delay_fn=lambda *a: 0)
        self.assertEqual(policy.choose(self.task, dcs, self.now, self.cluster), (1, False))

    def test_policy_can_route_to_future_available_center(self):
        dirty = FakeDC(1, carbon=600, cores=2)
        green = FakeDC(2, carbon=100, cores=0)
        runner = IdentityTask("busy", cpu=2)
        runner.finish_time = self.now + timedelta(minutes=30)
        green.running_tasks = [runner]
        dcs = {"dirty": dirty, "green": green}
        policy = QueueRiskCarbonPolicy("queue_risk_carbon", delay_fn=lambda *a: 0,
                                      risk_buffer_minutes=0)
        self.assertEqual(policy.choose(self.task, dcs, self.now, self.cluster), (2, False))

    def test_defer_budget_and_deadline_shield(self):
        dc = FakeDC(1, carbon=100)
        p = QueueRiskCarbonPolicy("queue_risk_defer", delay_fn=lambda *a: 0,
                                  risk_buffer_minutes=0, max_waits=1)
        for k in range(3):
            p.choose(self.task, {"one": dc}, self.now + timedelta(minutes=15*k), self.cluster)
        dc.carbon = 600
        self.assertEqual(
            p.choose(self.task, {"one": dc},
                     self.now + timedelta(minutes=45), self.cluster), (0, False))
        self.assertEqual(
            p.choose(self.task, {"one": dc},
                     self.now + timedelta(minutes=60), self.cluster), (1, False))
        self.assertEqual(p.waits[self.task], 1)

    def test_hard_deadline_prevents_wait(self):
        dc = FakeDC(1, carbon=100)
        p = QueueRiskCarbonPolicy("queue_risk_defer", delay_fn=lambda *a: 0)
        for k in range(3):
            p.choose(self.task, {"one": dc}, self.now + timedelta(minutes=15*k), self.cluster)
        dc.carbon = 600
        self.task.sla_deadline = self.now + timedelta(minutes=75)
        self.assertEqual(
            p.choose(self.task, {"one": dc}, self.now + timedelta(minutes=45),
                     self.cluster), (1, False))


if __name__ == "__main__":
    unittest.main()
