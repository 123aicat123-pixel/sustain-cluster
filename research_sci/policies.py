"""Transparent task-level spatial scheduling baselines for SustainCluster.

All policies use the same feasible-center set and the same network-delay
estimator. They never defer tasks, so this pilot isolates spatial selection.
Neither the estimated finish time nor current can_schedule() is an SLA guarantee.
"""
from datetime import timedelta
import math


class SpatialPolicy:
    NAMES = ("round_robin", "lowest_carbon", "fastest_finish", "sla_carbon")

    def __init__(self, name, delay_fn=None):
        if name not in self.NAMES:
            raise ValueError(f"Unknown policy: {name}")
        if delay_fn is None:
            from data.network_cost.network_delay import get_transmission_delay
            delay_fn = get_transmission_delay
        self.name = name
        self.delay_fn = delay_fn
        self._round_robin_last_id = None

    def choose(self, task, datacenters, current_time, cluster_manager, step_seconds=900):
        """Return (physical dc_id, no_capacity_fallback).

        If no center currently has capacity, route to the origin if present;
        otherwise route to the lowest-ID center. Record that fallback separately.
        The simulation queue, not this policy, determines eventual start time.
        """
        centers = sorted(datacenters.values(), key=lambda dc: dc.dc_id)
        if not centers:
            raise ValueError("Cannot schedule a task without data centers")
        ids = [dc.dc_id for dc in centers]
        if len(set(ids)) != len(ids):
            raise ValueError("Data-center IDs must be unique")
        candidates = [dc for dc in centers if dc.can_schedule(task)]
        if not candidates:
            chosen = next((dc for dc in centers if dc.dc_id == task.origin_dc_id), centers[0])
            return chosen.dc_id, True

        if self.name == "round_robin":
            eligible = [dc.dc_id for dc in candidates]
            chosen_id = next((i for i in eligible if self._round_robin_last_id is None or i > self._round_robin_last_id), eligible[0])
            self._round_robin_last_id = chosen_id
            return chosen_id, False

        origin = cluster_manager.get_dc_location(task.origin_dc_id)
        scored = []
        for dc in candidates:
            delay = float(self.delay_fn(origin, dc.location, cluster_manager.cloud_provider, task.bandwidth_gb))
            if not math.isfinite(delay) or delay < 0:
                raise ValueError(f"Invalid transmission delay: {delay}")
            # TaskSchedulingEnv processes new in-transit assignments on the NEXT tick.
            wait_ticks = max(1, math.ceil(delay / step_seconds))
            estimated_finish = (current_time + timedelta(seconds=step_seconds * wait_ticks)
                                + timedelta(minutes=float(task.duration)))
            carbon = float(dc.get_current_carbon_intensity(norm=False))
            if not math.isfinite(carbon):
                raise ValueError("Non-finite carbon intensity")
            scored.append((dc, estimated_finish, carbon))

        if self.name == "lowest_carbon":
            best = min(scored, key=lambda x: (x[2], x[1], x[0].dc_id))
        elif self.name == "fastest_finish":
            best = min(scored, key=lambda x: (x[1], x[2], x[0].dc_id))
        else:
            feasible_deadline = [x for x in scored if x[1] <= task.sla_deadline]
            if feasible_deadline:
                best = min(feasible_deadline, key=lambda x: (x[2], x[1], x[0].dc_id))
            else:
                best = min(scored, key=lambda x: (x[1], x[2], x[0].dc_id))
        return best[0].dc_id, False
