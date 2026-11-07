"""SLA-feasible carbon-aware routing baseline for a COMMON per-task action set.

This is a transparent research *baseline*, not the proposed novel algorithm.
It only performs spatial assignment (no postponement/forecasting). It computes
earliest delivery on SustainCluster's 15-minute action grid, selects the
cleanest currently schedulable data center whose predicted task finish meets
the deadline, otherwise selects the fastest predicted feasible location.
Predictions ignore future contention: no hard SLA guarantee is claimed.
"""
import math
from datetime import timedelta

from data.network_cost.network_delay import get_transmission_delay


class SLAFeasibleCarbonPolicy:
    def __init__(self, delay_fn=None):
        self.delay_fn = delay_fn or get_transmission_delay
        self.current_time = None
        self.cluster_manager = None

    def reset(self):
        self.current_time = None
        self.cluster_manager = None

    def set_context(self, current_time, cluster_manager):
        self.current_time = current_time
        self.cluster_manager = cluster_manager

    def __call__(self, task, datacenters, logger=None):
        if not datacenters:
            return None
        if self.current_time is None or self.cluster_manager is None:
            raise RuntimeError("set_context must be called before selecting an action")
        origin = self.cluster_manager.get_dc_location(task.origin_dc_id)
        provider = self.cluster_manager.cloud_provider
        step_seconds = 15 * 60
        scored = []
        for dc in datacenters.values():
            # Upstream can_schedule is a current-resource feasibility check,
            # not an estimate of future queue availability.
            if not dc.can_schedule(task):
                continue
            if dc.dc_id == task.origin_dc_id:
                # Local placement enters the pending queue immediately.
                wait_steps = 0
            else:
                delay_seconds = float(
                    self.delay_fn(origin, dc.location, provider, task.bandwidth_gb)
                )
                if not math.isfinite(delay_seconds) or delay_seconds < 0:
                    raise ValueError(f"invalid transmission delay: {delay_seconds}")
                # Remote transfers first become schedulable in a later step.
                wait_steps = max(1, math.ceil(delay_seconds / step_seconds))
            finish_estimate = (
                self.current_time
                + timedelta(seconds=wait_steps * step_seconds)
                + timedelta(minutes=float(task.duration))
            )
            carbon = float(dc.get_current_carbon_intensity(norm=False))
            price = float(dc.price_manager.get_current_price())
            scored.append({
                "dc": dc, "finish": finish_estimate,
                "carbon": carbon, "price": price,
            })
        if not scored:
            return None
        feasible = [s for s in scored if s["finish"] <= task.sla_deadline]
        if feasible:
            choice = min(
                feasible,
                key=lambda s: (
                    s["carbon"], s["price"], s["finish"], s["dc"].dc_id
                ),
            )
        else:
            choice = min(
                scored,
                key=lambda s: (
                    s["finish"], s["carbon"], s["price"], s["dc"].dc_id
                ),
            )
        return choice["dc"].dc_id
