"""Online *surrogate* NSGA-II batch routing policy for SustainCluster.

No future trace or true simulator metrics are used in decisions. Fitness is an
explicit heuristic estimate of incremental electricity cost, carbon, deadline
tardiness. This is a benchmark prototype, not an optimal or physically
calibrated multiobjective scheduler.

Each batch has a fixed evaluation budget: population 16, generations 8.
Randomness is locally seeded per policy run, separate from workload generation.
"""
from __future__ import annotations

import math
import random
from datetime import timedelta

from data.network_cost.network_delay import get_transmission_delay
from research.nsga2_core import nsga2_optimize
from research.sla_carbon_policy import SLAFeasibleCarbonPolicy


class NSGA2BatchPolicy:
    def __init__(self, *, seed=0, population=16, generations=8, delay_fn=None):
        self.seed = seed
        self.population = population
        self.generations = generations
        self.delay_fn = delay_fn or get_transmission_delay
        self.reset()

    def reset(self):
        self.rng = random.Random(self.seed)
        self.current_time = None
        self.cluster_manager = None
        self.optimizations = 0
        self.surrogate_evaluations = 0
        self.evaluation_requests = 0
        self.last_metrics = None

    def set_context(self, now, manager):
        self.current_time = now
        self.cluster_manager = manager

    def select_batch(self, tasks, datacenters):
        if not tasks:
            return [], 0
        if self.current_time is None or self.cluster_manager is None:
            raise RuntimeError("set_context must be called first")
        dcs = list(datacenters.values())
        if not dcs:
            raise ValueError("no data centers available")
        by_id = {dc.dc_id: dc for dc in dcs}
        if len(by_id) != len(dcs):
            raise ValueError("duplicate numeric data center IDs")
        # Physical input proxies: a CPU request and duration are not measured
        # energy. Normalize price in USD/MWh and CI in g/kWh consistently.
        choices = []
        best_heuristic = []
        fallback_count = 0
        heuristic = SLAFeasibleCarbonPolicy(delay_fn=self.delay_fn)
        heuristic.set_context(self.current_time, self.cluster_manager)
        for task in tasks:
            candidate = [dc.dc_id for dc in dcs if dc.can_schedule(task)]
            if not candidate:
                fallback_count += 1
                candidate = [task.origin_dc_id if task.origin_dc_id in by_id else min(by_id)]
            choices.append(candidate)
            h = heuristic(task, datacenters)
            best_heuristic.append(h if h in candidate else candidate[0])

        # Compute candidate-specific transfer and (optimistic) completion.
        # An additional load proxy reflects decisions within the same batch.
        locs = {}
        estimated = []
        for task, candidate in zip(tasks, choices):
            origin = task.origin_dc_id
            if origin not in locs:
                locs[origin] = self.cluster_manager.get_dc_location(origin)
            one = {}
            for dc_id in candidate:
                dc = by_id[dc_id]
                delay = 0.0 if dc_id == origin else float(self.delay_fn(
                    locs[origin], dc.location, self.cluster_manager.cloud_provider,
                    task.bandwidth_gb,
                ))
                if not math.isfinite(delay) or delay < 0:
                    raise ValueError("invalid network transfer delay")
                # Remote transfer is admitted into a later 15-minute step.
                transfer_minutes = 0 if dc_id == origin else max(
                    15.0, math.ceil(delay / 900) * 15.0
                )
                ci = float(dc.get_current_carbon_intensity(norm=False))
                price = float(dc.price_manager.get_current_price())
                if not math.isfinite(ci) or not math.isfinite(price):
                    raise ValueError("invalid price or carbon intensity")
                core_hours_proxy = float(task.cores_req) * float(task.duration) / 60.0
                energy_proxy_kwh = core_hours_proxy * 0.006  # 6 W/core, proxy only
                cost_proxy = energy_proxy_kwh * price / 1000.0
                carbon_proxy = energy_proxy_kwh * ci / 1000.0
                one[dc_id] = (cost_proxy, carbon_proxy, transfer_minutes)
            estimated.append(one)

        def evaluate(chrom):
            cost = carbon = tardiness = 0.0
            batch_load = {}
            for task, dc_id, cand in zip(tasks, chrom, estimated):
                dc = by_id[dc_id]
                cost_proxy, carbon_proxy, transfer_minutes = cand[dc_id]
                previous_cores = batch_load.get(dc_id, 0.0)
                # Approximate contention ONLY among tasks in current batch.
                # It is not simulator queue prediction or a real job-level
                # makespan evaluation.
                capacity = max(1.0, float(dc.available_cores))
                congestion = max(0.0, (previous_cores + float(task.cores_req)) / capacity - 1.0)
                queue_minutes = 15.0 * congestion
                finish = self.current_time + timedelta(
                    minutes=transfer_minutes + queue_minutes + float(task.duration)
                )
                tardiness += max(0.0, (finish-task.sla_deadline).total_seconds() / 60)
                cost += cost_proxy
                carbon += carbon_proxy
                batch_load[dc_id] = previous_cores + float(task.cores_req)
            return cost, carbon, tardiness

        chromosome, metrics = nsga2_optimize(
            choices, evaluate, population_size=self.population,
            generations=self.generations, rng=self.rng,
            seeds=[best_heuristic], weights=(0.1, 0.1, 0.8)
        )
        self.optimizations += 1
        self.surrogate_evaluations += metrics["surrogate_evaluations"]
        self.evaluation_requests += metrics["evaluation_requests"]
        self.last_metrics = metrics
        index = {dc.dc_id: i+1 for i, dc in enumerate(dcs)}
        return [index[g] for g in chromosome], fallback_count
