"""Causal, transparent temporal deferral baselines for SustainCluster.

These are controls, NOT an SCI algorithm novelty claim.
No future carbon-intensity ground truth, no unseen queue state.
The spatial fallback uses exactly the same SLA-carbon rule as pilot baselines.
"""
from collections import deque
from datetime import timedelta
import math

from research_sci.policies import SpatialPolicy


class TemporalPolicy:
    NAMES = ("slack_wait_once", "causal_carbon_wait")

    def __init__(self, name, delay_fn=None, window=8, threshold_pct=5.0,
                 max_waits=2, safety_minutes=0.0):
        if name not in self.NAMES:
            raise ValueError(f"Unknown temporal policy: {name}")
        if window < 2 or max_waits < 1 or threshold_pct < 0 or safety_minutes < 0:
            raise ValueError("Invalid temporal policy parameters")
        self.name = name
        self.delay_fn = delay_fn
        self.base = SpatialPolicy("sla_carbon", delay_fn=delay_fn)
        self.history = deque(maxlen=window)
        self.last_observed_time = None
        self.deferral_count = {}
        self.threshold_pct = threshold_pct
        self.max_waits = max_waits
        self.safety_minutes = safety_minutes
        self.ready_for_wait = 0

    def _observe(self, datacenters, time):
        if self.last_observed_time == time:
            return
        if self.last_observed_time is not None and time < self.last_observed_time:
            raise ValueError("Non-monotonic simulator time")
        intensities = [
            float(dc.get_current_carbon_intensity(norm=False))
            for dc in datacenters.values()
        ]
        if intensities and not all(math.isfinite(x) and x >= 0 for x in intensities):
            raise ValueError("Invalid observed carbon intensity")
        if intensities:
            self.history.append(min(intensities))
        self.last_observed_time = time

    def choose(self, task, datacenters, current_time, cluster_manager,
               step_seconds=900):
        self._observe(datacenters, current_time)
        dc_id, fallback = self.base.choose(
            task, datacenters, current_time, cluster_manager,
            step_seconds=step_seconds
        )
        if fallback:
            return dc_id, fallback
        if self.deferral_count.get(task, 0) >= self.max_waits:
            return dc_id, False

        dc = next(x for x in datacenters.values() if x.dc_id == dc_id)
        origin = cluster_manager.get_dc_location(task.origin_dc_id)
        if self.base.delay_fn is None:
            # SpatialPolicy initializes its own delay function.
            raise AssertionError("No transmission delay estimator")
        transfer_seconds = float(self.base.delay_fn(
            origin, dc.location, cluster_manager.cloud_provider, task.bandwidth_gb))
        if not math.isfinite(transfer_seconds) or transfer_seconds < 0:
            raise ValueError("Invalid transmission delay")
        delivery_ticks = max(1, math.ceil(transfer_seconds / step_seconds))
        estimated_finish_if_wait = (
            current_time
            + timedelta(seconds=(delivery_ticks + 1) * step_seconds)
            + timedelta(minutes=float(task.duration) + self.safety_minutes)
        )
        # Explicitly forbid deferring if an extra scheduling tick would
        # violate even the optimistic completion estimate.
        if estimated_finish_if_wait > task.sla_deadline:
            return dc_id, False
        self.ready_for_wait += 1

        if self.name == "slack_wait_once":
            should_wait = self.deferral_count.get(task, 0) == 0
        else:
            # Never look ahead. Compare CURRENT best grid intensity with
            # past seen intensities using a historical lower quartile.
            if len(self.history) < 4:
                return dc_id, False
            ranked = sorted(self.history)
            reference = ranked[max(0, (len(ranked) - 1) // 4)]
            current = min(float(x.get_current_carbon_intensity(norm=False))
                          for x in datacenters.values())
            should_wait = current > reference * (1.0 + self.threshold_pct / 100.0)

        if should_wait:
            self.deferral_count[task] = self.deferral_count.get(task, 0) + 1
            # Environment action slot zero means defer; not a DC ID.
            return 0, False
        return dc_id, False
