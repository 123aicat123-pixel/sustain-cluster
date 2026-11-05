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
from research_sci.online_calibration import OnlineResidualCalibrator
from research_sci.queue_discipline import priority_key, VALID_QUEUE_ORDERS


_RESOURCE_KEYS = ("cores_req", "gpu_req", "mem_req")
_AVAILABLE_KEYS = ("available_cores", "available_gpus", "available_mem")


def predict_finish(task, dc, now, arrival_ticks, step_seconds=900, max_ticks=192,
                   known_arrivals=(), queue_order="fifo"):
    """Predict completion from observed FIFO queue and running allocations.

    Returns None if target cannot be scheduled within max_ticks. The discrete
    model mirrors currently known capacity releases and FIFO scheduling but
    necessarily omits future arrivals, placement conflicts and forecast errors.
    """
    if step_seconds <= 0 or arrival_ticks < 1 or max_ticks < arrival_ticks:
        raise ValueError("Invalid forecasting horizon")
    if queue_order not in VALID_QUEUE_ORDERS:
        raise ValueError("Unsupported queue order")
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
    # Commitments include already-in-transit jobs and earlier selections
    # in this very same decision batch. Arrival timestamps are observed or
    # computed from known transmission delay, never future workload arrivals.
    arrivals = sorted(known_arrivals, key=lambda x: x[0])
    seen = {task}
    for _, known_task in arrivals:
        if known_task in seen:
            raise AssertionError("Duplicate target / known arrival in forecast")
        seen.add(known_task)
    arrival_index = 0
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
        while arrival_index < len(arrivals) and arrivals[arrival_index][0] <= tick_time:
            waiting.append(arrivals[arrival_index][1])
            arrival_index += 1
        if tick == arrival_ticks:
            waiting.append(task)
        # Exactly mirror the opt-in datacenter EDF execution order.
        # FIFO remains byte-for-byte unchanged when queue_order='fifo'.
        if queue_order == "edf":
            waiting = deque(sorted(waiting, key=priority_key))
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
    NAMES = ("queue_risk_carbon", "queue_risk_defer",
             "queue_calibrated_carbon", "queue_calibrated_defer")

    def __init__(self, name, delay_fn=None, risk_buffer_minutes=30,
                 wait_threshold_pct=5.0, max_waits=2, history_window=8,
                 queue_order="fifo"):
        if name not in self.NAMES:
            raise ValueError(f"Unknown queue policy {name}")
        if queue_order not in VALID_QUEUE_ORDERS:
            raise ValueError("Unsupported queue order")
        if risk_buffer_minutes < 0 or wait_threshold_pct < 0 or max_waits < 1 or history_window < 4:
            raise ValueError("Invalid queue policy settings")
        self.name = name
        self.queue_order = queue_order
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
        self.known_arrivals_by_dc = {}
        self.calibrator = (OnlineResidualCalibrator()
                           if name.startswith("queue_calibrated_") else None)
        self.margins_used = []
        self.calibration_ready_decisions = 0
        self.dispatch_margin_by_task = {}
        self.dispatch_prediction_by_task = {}

    def buffer_minutes(self):
        return (self.calibrator.margin_minutes() if self.calibrator is not None
                else self.risk_buffer.total_seconds() / 60)

    def set_visible_commitments(self, known_arrivals_by_dc):
        """Visible in-transit and same-batch committed routes only."""
        self.known_arrivals_by_dc = known_arrivals_by_dc

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
            finish = predict_finish(
                task, dc, current_time, ticks, step_seconds,
                known_arrivals=self.known_arrivals_by_dc.get(dc.dc_id, ()),
                queue_order=self.queue_order
            )
            if finish is None:
                continue
            carbon = float(dc.get_current_carbon_intensity(norm=False))
            current_resource_feasible = dc.can_schedule(task)
            if not current_resource_feasible:
                self.estimated_queuing_actions += 1
            estimates.append((finish, carbon, dc.dc_id, ticks))

        if not estimates:
            self.dispatch_margin_by_task[task] = self.buffer_minutes()
            self.dispatch_prediction_by_task[task] = None
            self.no_forecast += 1
            fallback = next((x.dc_id for x in centers if x.dc_id == task.origin_dc_id),
                            centers[0].dc_id)
            return fallback, True

        buffer_min = self.buffer_minutes()
        self.margins_used.append(buffer_min)
        if (self.calibrator is not None
                and len(self.calibrator.residuals) >= self.calibrator.min_samples):
            self.calibration_ready_decisions += 1
        buffer = timedelta(minutes=buffer_min)
        feasible = [x for x in estimates if x[0] + buffer <= task.sla_deadline]
        if feasible:
            best = min(feasible, key=lambda x: (x[1], x[0], x[2]))
        else:
            best = min(estimates, key=lambda x: (x[0], x[1], x[2]))

        if self.name in ("queue_risk_defer", "queue_calibrated_defer") and len(self.history) >= 4:
            predicted_finish, _, best_id, _ = best
            # A candidate with no true slack cannot be deferred safely even in
            # this optimistic forecast. The buffer is an explicit assumption.
            remaining_slack = task.sla_deadline - (predicted_finish + buffer)
            if remaining_slack >= timedelta(seconds=step_seconds):
                self.ready_for_wait += 1
                ordered = sorted(self.history)
                historic_low = ordered[(len(ordered) - 1) // 4]
                now_min = self.history[-1]
                if (self.waits.get(task, 0) < self.max_waits and
                        now_min > historic_low * (1 + self.wait_threshold_pct / 100)):
                    self.waits[task] = self.waits.get(task, 0) + 1
                    return 0, False
        # Store only a genuinely committed (non-deferred) decision margin.
        # This remains frozen after later completions update the calibrator.
        self.dispatch_margin_by_task[task] = buffer_min
        self.dispatch_prediction_by_task[task] = best[0]
        return best[2], False
