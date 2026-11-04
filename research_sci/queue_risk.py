"""Queue-aware carbon scheduling baseline based only on presently observable state.

The estimator simulates known running tasks' remaining times and the current
FIFO pending queue at 15-minute ticks. It assumes NO future task arrivals
and does NOT observe hidden future carbon intensity or runtime outcomes.
This is a queue forecast baseline, not a validated probabilistic SLA guarantee.
"""
from collections import deque
from datetime import timedelta
import math

from research_sci.policies import SpatialPolicy


_RESOURCE_KEYS = ("cores_req", "gpu_req", "mem_req")
_AVAILABLE_KEYS = ("available_cores", "available_gpus", "available_mem")


def predict_finish(task, dc, now, arrival_ticks, step_seconds=900, max_ticks=192):
    """Predict completion from observed FIFO queue and running allocations.

    Returns None if target cannot be scheduled within max_ticks. The discrete
    model mirrors currently known capacity releases and FIFO scheduling but
    necessarily omits future arrivals, placement conflicts and forecast errors.
    """
    if step_seconds <= 0 or arrival_ticks < 1 or max_ticks < arrival_ticks:
        raise ValueError("Invalid forecasting horizon")
    available = [float(getattr(dc, key)) for key in _AVAILABLE_KEYS]
    for value in available:
        if not math.isfinite(value) or value < -1e-6:
            raise ValueError("Invalid available capacity")
    running = []
    for existing in dc.running_tasks:
        finish = getattr(existing, "finish_time", None)
        if finish is None:
            raise ValueError("Running task missing finish_time")
        running.append((finish, [float(getattr(existing, key)) for key in _RESOURCE_KEYS]))
    waiting = deque(dc.pending_tasks)
    time_delta = timedelta(seconds=step_seconds)
    for tick in range(max_ticks + 1):
        tick_time = now + tick * time_delta
        next_running = []
        for end, requirements in running:
            if end <= tick_time:
                for idx, amount in enumerate(requirements):
                    available[idx] += amount
            else:
                next_running.append((end, requirements))
        running = next_running
        if tick == arrival_ticks:
            waiting.append(task)
        queue_size = len(waiting)
        for _ in range(queue_size):
            candidate = waiting.popleft()
            req = [float(getattr(candidate, key)) for key in _RESOURCE_KEYS]
            if any(not math.isfinite(x) or x < 0 for x in req):
                raise ValueError("Invalid resource demand")
            if all(demand <= free + 1e-8 for demand, free in zip(req, available)):
                for idx, amount in enumerate(req):
                    available[idx] -= amount
                finish = tick_time + timedelta(minutes=float(candidate.duration))
                if candidate is task:
                    return finish
                running.append((finish, req))
            else:
                waiting.append(candidate)
    return None


class QueueRiskCarbonPolicy:
    """Spatial or cautious temporal baseline using estimated queue completion.

    queue_risk_carbon: choose least carbon among optimistic on-time candidates;
    otherwise choose earliest predicted completion.
    queue_risk_defer: same placement, optionally defer when (a) historical
    carbon has been lower and (b) conservative queue estimate still leaves
    enough SLA slack. This is causal and heuristic, not a risk guarantee.
    """
    NAMES = ("queue_risk_carbon", "queue_risk_defer")

    def __init__(self, name, delay_fn=None, risk_buffer_minutes=30,
                 wait_threshold_pct=5.0, max_waits=2, history_window=8):
        if name not in self.NAMES:
            raise ValueError(f"Unknown queue policy {name}")
        if risk_buffer_minutes < 0 or wait_threshold_pct < 0 or max_waits < 1 or history_window < 4:
            raise ValueError("Invalid queue policy settings")
        self.name = name
        self.delay_fn = SpatialPolicy("sla_carbon", delay_fn=delay_fn).delay_fn
        self.risk_buffer = timedelta(minutes=risk_buffer_minutes)
        self.wait_threshold_pct = wait_threshold_pct
        self.max_waits = max_waits
        self.history = deque(maxlen=history_window)
        self.last_observed_time = None
        self.waits = {}
        self.ready_for_wait = 0
        self.estimated_queuing_actions = 0
        self.no_forecast = 0

    def _observe(self, datacenters, now):
        if self.last_observed_time == now:
            return
        if self.last_observed_time is not None and now < self.last_observed_time:
            raise ValueError("Clock went backwards")
        intensities = [float(dc.get_current_carbon_intensity(norm=False))
                       for dc in datacenters.values()]
        if intensities:
            if not all(math.isfinite(x) and x >= 0 for x in intensities):
                raise ValueError("Bad carbon intensity")
            self.history.append(min(intensities))
        self.last_observed_time = now

    def choose(self, task, datacenters, current_time, cluster_manager, step_seconds=900):
        centers = sorted(datacenters.values(), key=lambda x: x.dc_id)
        if not centers:
            raise ValueError("No data centers")
        self._observe(datacenters, current_time)
        origin_loc = cluster_manager.get_dc_location(task.origin_dc_id)
        estimates = []
        for dc in centers:
            delay = float(self.delay_fn(
                origin_loc, dc.location, cluster_manager.cloud_provider, task.bandwidth_gb))
            if not math.isfinite(delay) or delay < 0:
                raise ValueError("Invalid transmission delay")
            ticks = max(1, math.ceil(delay / step_seconds))
            finish = predict_finish(task, dc, current_time, ticks, step_seconds)
            if finish is None:
                continue
            carbon = float(dc.get_current_carbon_intensity(norm=False))
            current_resource_feasible = dc.can_schedule(task)
            if not current_resource_feasible:
                self.estimated_queuing_actions += 1
            estimates.append((finish, carbon, dc.dc_id, ticks))

        if not estimates:
            self.no_forecast += 1
            fallback = next((x.dc_id for x in centers if x.dc_id == task.origin_dc_id),
                            centers[0].dc_id)
            return fallback, True

        feasible = [x for x in estimates if x[0] + self.risk_buffer <= task.sla_deadline]
        if feasible:
            best = min(feasible, key=lambda x: (x[1], x[0], x[2]))
        else:
            best = min(estimates, key=lambda x: (x[0], x[1], x[2]))

        if self.name == "queue_risk_defer" and len(self.history) >= 4:
            predicted_finish, _, best_id, _ = best
            # A candidate with no true slack cannot be deferred safely even in
            # this optimistic forecast. The buffer is an explicit assumption.
            remaining_slack = task.sla_deadline - (predicted_finish + self.risk_buffer)
            if remaining_slack >= timedelta(seconds=step_seconds):
                self.ready_for_wait += 1
                ordered = sorted(self.history)
                historic_low = ordered[(len(ordered) - 1) // 4]
                now_min = self.history[-1]
                if (self.waits.get(task, 0) < self.max_waits and
                        now_min > historic_low * (1 + self.wait_threshold_pct / 100)):
                    self.waits[task] = self.waits.get(task, 0) + 1
                    return 0, False
        return best[2], False
