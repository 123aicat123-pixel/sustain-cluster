"""Queue-aware, transmission-accounting online NSGA-II research prototype.

The queue predictor uses only running finish times, current pending queues,
the currently admitted batch, and publicly/currently observed energy-price and
carbon signals. It NEVER looks at future workload rows or future CI/price.

This is a pre-publication HYPOTHESIS, not an established novel method.
Ablations keep the same chromosome, feasible action choices, optimizer and
evaluation budget: (1) no current queue model; (2) no transfer externality
in cost/carbon, but still enforce transfer *latency* for SLA predictions.

Reported optimizer fitness is an explicitly approximate incremental proxy;
final results always come from the independent full simulator.
"""
from __future__ import annotations

from collections import deque
from datetime import timedelta
import math

from data.network_cost.network_delay import get_transmission_delay
from research.nsga2_batch_policy import NSGA2BatchPolicy
from research.nsga2_core import nsga2_optimize
from research.transit_front_carbon import choose_front_carbon_under_risk
from research.sla_carbon_policy import SLAFeasibleCarbonPolicy
from utils.transmission_region_mapper import map_location_to_region


STEP_MINUTES = 15
STEP = timedelta(minutes=STEP_MINUTES)


def carbon_guard_choice(optimized, reference, evaluate, margin=0.0):
    """Limit SURROGATE carbon against a legal reference chromosome.

    This cannot guarantee real facility carbon, because its fitness model
    omits many physical effects. This is an experimental policy gate.
    """
    if not math.isfinite(margin) or margin < 0:
        raise ValueError("carbon guard margin must be nonnegative and finite")
    optimized_score = tuple(evaluate(optimized))
    reference_score = tuple(evaluate(reference))
    if len(optimized_score) != 3 or len(reference_score) != 3:
        raise ValueError("surrogate fitness must return three objectives")
    if any(not math.isfinite(float(x)) for x in optimized_score + reference_score):
        raise ValueError("nonfinite surrogate score")
    baseline_carbon = float(reference_score[1])
    limit = baseline_carbon + margin * max(abs(baseline_carbon), 1e-9)
    if float(optimized_score[1]) > limit + 1e-12:
        return list(reference), True
    return list(optimized), False


def carbon_sla_guard_choice(optimized, reference, evaluate, margin=0.0):
    """Proxy-carbon guard with a ZERO extra predicted-tardiness budget.

    Lower proxy carbon may select the reference only when its predicted
    total tardiness does not exceed that of the optimized chromosome.
    This cannot guarantee true SLA compliance under future contention.
    Returns (chromosome, intervened, risk_vetoed).
    """
    if not math.isfinite(margin) or margin < 0:
        raise ValueError("carbon margin must be nonnegative and finite")
    scores_opt = tuple(evaluate(optimized))
    scores_ref = tuple(evaluate(reference))
    if len(scores_opt) != 3 or len(scores_ref) != 3:
        raise ValueError("expected three objectives")
    if any(not math.isfinite(float(v)) for v in scores_opt + scores_ref):
        raise ValueError("nonfinite surrogate scores")
    baseline_carbon = float(scores_ref[1])
    limit = baseline_carbon + margin * max(abs(baseline_carbon), 1e-9)
    exceeds_carbon = float(scores_opt[1]) > limit + 1e-12
    if not exceeds_carbon:
        return list(optimized), False, False
    if float(scores_ref[2]) > float(scores_opt[2]) + 1e-12:
        return list(optimized), False, True
    return list(reference), True, False


def predict_starts(dc, arrivals, now, max_steps=672):
    """Predict new-task start timestamps by simulating CURRENT FIFO queues.

    `arrivals` holds (new_task, datetime eligible) in decision-batch order.
    Current running tasks retain their *known* finish timestamps. Existing
    pending tasks precede new arrivals at each simulated 15-minute tick.
    No future externally arriving tasks are included.

    Returns {new_task: predicted_start}. Raises if a task cannot fit
    physical capacity, or cannot start within the seven-day projection.
    """
    available = [
        float(dc.available_cores), float(dc.available_gpus),
        float(dc.available_mem),
    ]
    total = [
        float(dc.total_cores), float(dc.total_gpus),
        float(dc.total_mem_GB),
    ]
    req = lambda t: (float(t.cores_req), float(t.gpu_req), float(t.mem_req))
    if any(any(x > maximum + 1e-8 for x, maximum in zip(req(task), total))
           for task, _ in arrivals):
        raise ValueError("new task exceeds total data center resources")
    scheduled = [(task.finish_time, task) for task in dc.running_tasks]
    if any(when is None for when, _ in scheduled):
        raise ValueError("running task has no finish timestamp")
    queue = deque(dc.pending_tasks)
    waiting = sorted(enumerate(arrivals), key=lambda x: (x[1][1], x[0]))
    cursor = 0
    begins = {}
    for step in range(max_steps + 1):
        tick = now + step * STEP
        still_running = []
        for finish, task in scheduled:
            if finish <= tick:
                available = [a + x for a, x in zip(available, req(task))]
            else:
                still_running.append((finish, task))
        scheduled = still_running
        # Only the presently assigned tasks in this batch are admitted here.
        while cursor < len(waiting) and waiting[cursor][1][1] <= tick:
            queue.append(waiting[cursor][1][0])
            cursor += 1
        for _ in range(len(queue)):
            task = queue.popleft()
            resources = req(task)
            if all(a + 1e-8 >= x for a, x in zip(available, resources)):
                available = [a - x for a, x in zip(available, resources)]
                end = tick + timedelta(minutes=float(task.duration))
                scheduled.append((end, task))
                if task in dict(arrivals):
                    if task in begins:
                        raise AssertionError("new task scheduled twice")
                    begins[task] = tick
            else:
                queue.append(task)
        if len(begins) == len(arrivals):
            return begins
    raise RuntimeError("queue projection exhausted: choose longer horizon")


def predict_starts_with_in_transit(dc, new_arrivals, now, pending_transit):
    """Project starts with tasks ALREADY routed to this DC and still in transit.

    `pending_transit` has (arrival_timestamp, task) tuples for this DC.
    Existing transit items are put before newly dispatched tasks at equal
    arrival ticks, as the simulator processes in_transit before actions.
    This is a predictor hypothesis; no future task arrivals are used.
    """
    merged = [(task, max(now, arrival)) for arrival, task in pending_transit]
    merged.extend(new_arrivals)
    if not new_arrivals:
        return {}
    if len({id(t) for t, _ in merged}) != len(merged):
        raise AssertionError("task duplicated in current action and in-transit")
    projection = predict_starts(dc, merged, now)
    return {task: projection[task] for task, _ in new_arrivals}


class QueueAwareNSGA2Policy(NSGA2BatchPolicy):
    """Fixed-budget routing with queue-model / transfer-accounting ablations."""

    def __init__(self, *, seed=0, population=16, generations=8,
                 delay_fn=None, queue_aware=True, transfer_accounting=True,
                 carbon_guard_margin=None, sla_safe_guard=False):
        self.queue_aware = queue_aware
        self.transfer_accounting = transfer_accounting
        self.carbon_guard_margin = carbon_guard_margin
        self.sla_safe_guard = bool(sla_safe_guard)
        if self.sla_safe_guard and self.carbon_guard_margin is None:
            raise ValueError("SLA-safe guard requires explicit carbon margin")
        if carbon_guard_margin is not None and (
            not math.isfinite(carbon_guard_margin) or carbon_guard_margin < 0
        ):
            raise ValueError("invalid carbon guard margin")
        super().__init__(seed=seed, population=population,
                         generations=generations, delay_fn=delay_fn)

    def reset(self):
        super().reset()
        self.carbon_guard_checks = 0
        self.carbon_guard_interventions = 0
        self.carbon_guard_vetoes = 0
        self.carbon_guard_extra_fitness_calls = 0
        self.predicted_start_by_task = {}
        self.prediction_audit_calls = 0

    def _project_starts(self, dc, arrivals, now):
        return predict_starts(dc, arrivals, now)

    def select_batch(self, tasks, datacenters):
        if not tasks:
            return [], 0
        if self.current_time is None or self.cluster_manager is None:
            raise RuntimeError("set_context must be called first")
        dcs = list(datacenters.values())
        if not dcs:
            raise ValueError("empty data center set")
        by_id = {dc.dc_id: dc for dc in dcs}
        if len(by_id) != len(dcs):
            raise ValueError("duplicate data center IDs")
        manager = self.cluster_manager
        now = self.current_time
        heuristic = SLAFeasibleCarbonPolicy(delay_fn=self.delay_fn)
        heuristic.set_context(now, manager)
        choices, heuristic_seed, fallback_count = [], [], 0
        # Same TOTAL-resource feasible set across all ablations. A busy DC
        # remains a legal routing action; jobs can wait in its pending FIFO.
        for task in tasks:
            candidate = [
                dc.dc_id for dc in dcs
                if task.cores_req <= dc.total_cores
                and task.gpu_req <= dc.total_gpus
                and task.mem_req <= dc.total_mem_GB
            ]
            if not candidate:
                fallback_count += 1
                candidate = [
                    task.origin_dc_id if task.origin_dc_id in by_id
                    else min(by_id)
                ]
            choices.append(candidate)
            h = heuristic(task, datacenters)
            heuristic_seed.append(h if h in candidate else candidate[0])

        estimated = []
        for task, candidate in zip(tasks, choices):
            origin = by_id[task.origin_dc_id]
            original_location = origin.location
            origin_region = map_location_to_region(original_location,
                                                   manager.cloud_provider)
            origin_ci = float(origin.ci_manager.get_current_ci(norm=False))
            one = {}
            for dc_id in candidate:
                dest = by_id[dc_id]
                if dc_id == task.origin_dc_id:
                    transfer_mins = 0
                    transfer_cost = 0
                    transfer_carbon = 0
                else:
                    delay = float(self.delay_fn(
                        original_location, dest.location,
                        manager.cloud_provider, task.bandwidth_gb
                    ))
                    if not math.isfinite(delay) or delay < 0:
                        raise ValueError("invalid transfer delay")
                    transfer_mins = max(STEP_MINUTES,
                                        math.ceil(delay / (STEP_MINUTES * 60))
                                        * STEP_MINUTES)
                    dest_region = map_location_to_region(dest.location,
                                                         manager.cloud_provider)
                    transfer_cost = (float(manager.transmission_matrix.loc[
                        origin_region, dest_region
                    ]) * float(task.bandwidth_gb))
                    transfer_carbon = (
                        0.06 * float(task.bandwidth_gb) * origin_ci / 1000
                    )
                # Explicit 6W/core energy proxy, NOT physical DC energy.
                e_kwh = float(task.cores_req) * float(task.duration) / 60 * 0.006
                price = float(dest.price_manager.get_current_price())
                ci = float(dest.get_current_carbon_intensity(norm=False))
                if not all(math.isfinite(v) for v in
                           (price, ci, origin_ci, transfer_cost, transfer_carbon)):
                    raise ValueError("nonfinite observed prices/carbon")
                cost = e_kwh * price / 1000
                carbon = e_kwh * ci / 1000
                if self.transfer_accounting:
                    cost += transfer_cost
                    carbon += transfer_carbon
                one[dc_id] = (cost, carbon, transfer_mins)
            estimated.append(one)

        # Store task-level predicted deadline misses alongside each *existing*
        # surrogate evaluation. No future simulation outcomes or added GA calls.
        predicted_miss_counts = {}

        def fitness(chrom):
            cost = carbon = tardiness = 0.0
            missed_deadlines = 0
            arrivals = {dc.dc_id: [] for dc in dcs}
            for task, dc_id, candidate_metrics in zip(tasks, chrom, estimated):
                c, co, delay_mins = candidate_metrics[dc_id]
                cost += c
                carbon += co
                arrivals[dc_id].append((task, now + timedelta(minutes=delay_mins)))

            if self.queue_aware:
                start_times = {}
                for dc in dcs:
                    if arrivals[dc.dc_id]:
                        start_times.update(self._project_starts(dc, arrivals[dc.dc_id], now))
            else:
                start_times = {
                    task: ready for incoming in arrivals.values()
                    for task, ready in incoming
                }
            for task in tasks:
                predicted_finish = start_times[task] + timedelta(
                    minutes=float(task.duration)
                )
                delay = (predicted_finish-task.sla_deadline).total_seconds()/60
                tardiness += max(0.0, delay)
                missed_deadlines += int(delay > 1e-9)
            predicted_miss_counts[tuple(chrom)] = missed_deadlines
            return cost, carbon, tardiness

        chromosome, metrics = nsga2_optimize(
            choices, fitness, population_size=self.population,
            generations=self.generations, rng=self.rng,
            seeds=[heuristic_seed], weights=(0.1, 0.1, 0.8)
        )
        if getattr(self, "front_carbon_risk_enabled", False):
            initial = tuple(chromosome)
            chromosome, changed = choose_front_carbon_under_risk(
                chromosome, metrics["final_front_records"], predicted_miss_counts
            )
            self.front_carbon_selection_checks += 1
            self.front_carbon_selection_changes += int(changed)
            # Chosen chromosome MUST be on the final optimizer front.
            if changed and tuple(chromosome) == initial:
                raise AssertionError("front selector intervention without change")
        if self.carbon_guard_margin is not None:
            self.carbon_guard_checks += 1
            if self.sla_safe_guard:
                chromosome, intervened, vetoed = carbon_sla_guard_choice(
                    chromosome, heuristic_seed, fitness, margin=self.carbon_guard_margin
                )
                self.carbon_guard_vetoes += int(vetoed)
            else:
                chromosome, intervened = carbon_guard_choice(
                    chromosome, heuristic_seed, fitness, margin=self.carbon_guard_margin
                )
            self.carbon_guard_extra_fitness_calls += 2
            self.carbon_guard_interventions += int(intervened)
        self.optimizations += 1
        self.surrogate_evaluations += metrics["surrogate_evaluations"]
        self.evaluation_requests += metrics["evaluation_requests"]
        self.last_metrics = metrics
        # Observational auditing only, performed AFTER action selection.
        # This does not influence the chromosome or its NSGA-II fitness.
        if self.queue_aware:
            selected_arrivals = {dc.dc_id: [] for dc in dcs}
            for task, dc_id, candidate_metrics in zip(tasks, chromosome, estimated):
                delay_mins = candidate_metrics[dc_id][2]
                selected_arrivals[dc_id].append(
                    (task, now + timedelta(minutes=delay_mins))
                )
            for dc in dcs:
                if selected_arrivals[dc.dc_id]:
                    prediction = self._project_starts(
                        dc, selected_arrivals[dc.dc_id], now
                    )
                    if set(prediction).intersection(self.predicted_start_by_task):
                        raise AssertionError("task dispatched/predicted twice")
                    self.predicted_start_by_task.update(prediction)
            self.prediction_audit_calls += 1
        to_action = {dc.dc_id: i+1 for i, dc in enumerate(dcs)}
        return [to_action[gene] for gene in chromosome], fallback_count


class QueueAwareWithTransit(QueueAwareNSGA2Policy):
    """Controlled in-transit queue ablation, all other NSGA-II settings equal."""

    def __init__(self, **kwargs):
        super().__init__(queue_aware=True, transfer_accounting=True, **kwargs)

    def reset(self):
        super().reset()
        self._pending_transit_by_dc = {}

    def set_in_transit(self, in_transit_items, datacenters):
        # Input comes from environment.in_transit_tasks at decision time,
        # before dispatching the current task batch.
        by_dc = {dc.dc_id: [] for dc in datacenters.values()}
        for arrival_time, task, dc_name in in_transit_items:
            if dc_name not in datacenters:
                raise ValueError(f"unknown in-transit destination {dc_name}")
            dc_id = datacenters[dc_name].dc_id
            by_dc[dc_id].append((arrival_time, task))
        self._pending_transit_by_dc = by_dc

    def _project_starts(self, dc, arrivals, now):
        return predict_starts_with_in_transit(
            dc, arrivals, now,
            self._pending_transit_by_dc.get(dc.dc_id, []),
        )


def relevant_transit_competition(dc, arrivals, now, pending_transit):
    """Check whether observed incoming transfers *could* change batch starts.

    Conservative deterministic gate: only skip transit projection when no
    transfer can arrive by the last base-predicted start, OR when there is
    no running/pending load and enough currently available CPU/GPU/memory
    to start every relevant transit task and every new task together.
    No future workload, realized completion, carbon or SLA labels used.

    Returns (transit_relevant, naive_prediction). It may over-trigger,
    but the no-overlap and full-capacity skip cases are safe shortcuts
    for this simplified FIFO queue model. No empirical threshold is tuned.
    """
    if not arrivals:
        return False, {}
    naive = predict_starts(dc, arrivals, now)
    if not pending_transit:
        return False, naive
    latest_base_start = max(naive.values())
    relevant = [
        (eta, task) for eta, task in pending_transit
        if max(now, eta) <= latest_base_start
    ]
    if not relevant:
        return False, naive
    if dc.running_tasks or dc.pending_tasks:
        return True, naive
    tasks = [task for task, _ in arrivals] + [task for _, task in relevant]
    capacity = (float(dc.available_cores), float(dc.available_gpus),
                float(dc.available_mem))
    required = (
        sum(float(t.cores_req) for t in tasks),
        sum(float(t.gpu_req) for t in tasks),
        sum(float(t.mem_req) for t in tasks),
    )
    return any(x > limit + 1e-8 for x, limit in zip(required, capacity)), naive


def transit_may_compete_fast(dc, arrivals, now, pending_transit):
    """Conservative O(number of tasks) gate, no base projection pre-pass.

    False means the full With-Transit projection and the base predictor
    MUST have the same new-task start times under the simulator's FIFO
    discrete-time abstraction. True means simulate all observable transit
    once. This rule is a computation shortcut, NOT carbon/SLA gating.
    """
    if not arrivals or not pending_transit:
        return False
    arrival_ids = {id(task) for task, _ in arrivals}
    if len(arrival_ids) != len(arrivals):
        raise AssertionError("duplicate task in new arrivals")
    if any(id(task) in arrival_ids for _, task in pending_transit):
        raise AssertionError("task duplicated in current action and in-transit")
    if dc.running_tasks or dc.pending_tasks:
        return True
    limits = (float(dc.available_cores), float(dc.available_gpus),
              float(dc.available_mem))
    total = (float(dc.total_cores), float(dc.total_gpus),
             float(dc.total_mem_GB))
    def required(tasks):
        return (
            sum(float(t.cores_req) for t in tasks),
            sum(float(t.gpu_req) for t in tasks),
            sum(float(t.mem_req) for t in tasks),
        )
    # Invalid tasks must still follow the projection's capacity exception.
    transit_tasks = [task for _, task in pending_transit]
    all_tasks = [task for task, _ in arrivals] + transit_tasks
    if any(any(v > bound + 1e-8 for v, bound in
               zip(required([task]), total)) for task in all_tasks):
        return True
    if all(x <= limit + 1e-8 for x, limit in zip(required(all_tasks), limits)):
        return False
    # Every new task can occupy capacity at the current tick, before any
    # in-transit task becomes eligible; starts are then already determined.
    if (all(ready <= now for _, ready in arrivals)
            and all(max(now, eta) > now for eta, _ in pending_transit)
            and all(x <= limit + 1e-8 for x, limit in zip(
                required([task for task, _ in arrivals]), limits))):
        return False
    return True


class QueueAwareCongestionAdaptive(QueueAwareWithTransit):
    """Conditional transit-state queue projection, exploratory ablation.

    The policy keeps the *exact* genetic algorithm, chromosome, action
    candidates and weights of WithTransit. It uses a no-parameter capacity
    relevance gate to skip unnecessary in-transit projection. The selection
    and actual simulator metrics still require fresh comparison. Projection
    counters include repeated fitness evaluations and the final audit call;
    they are NOT counts of distinct online decision epochs.
    """

    def reset(self):
        super().reset()
        self.adaptive_projection_checks = 0
        self.adaptive_transit_projections = 0
        self.adaptive_base_projections = 0

    def _project_starts(self, dc, arrivals, now):
        self.adaptive_projection_checks += 1
        pending = self._pending_transit_by_dc.get(dc.dc_id, [])
        if transit_may_compete_fast(dc, arrivals, now, pending):
            self.adaptive_transit_projections += 1
            return predict_starts_with_in_transit(dc, arrivals, now, pending)
        self.adaptive_base_projections += 1
        return predict_starts(dc, arrivals, now)


class QueueAwareFrontCarbonRisk(QueueAwareWithTransit):
    """Choose lower-proxy-carbon final-front solutions under no added
    *predicted* deadline misses/tardiness relative to standard knee.

    Changes only post-search choice, keeping population, generations,
    initial solutions, and evaluated action candidates identical.
    Does NOT guarantee realized SLA nor measured facility carbon.
    """

    front_carbon_risk_enabled = True

    def reset(self):
        super().reset()
        self.front_carbon_selection_checks = 0
        self.front_carbon_selection_changes = 0


class QueueAwareCarbonSlaGuard(QueueAwareNSGA2Policy):
    def __init__(self, **kwargs):
        super().__init__(queue_aware=True, transfer_accounting=True,
                         carbon_guard_margin=0.0, sla_safe_guard=True, **kwargs)


class QueueAwareCarbonGuard(QueueAwareNSGA2Policy):
    def __init__(self, **kwargs):
        super().__init__(queue_aware=True, transfer_accounting=True,
                         carbon_guard_margin=0.0, **kwargs)


class QueueAwareFull(QueueAwareNSGA2Policy):
    def __init__(self, **kwargs):
        super().__init__(queue_aware=True, transfer_accounting=True, **kwargs)


class QueueAblationNoQueue(QueueAwareNSGA2Policy):
    def __init__(self, **kwargs):
        super().__init__(queue_aware=False, transfer_accounting=True, **kwargs)


class QueueAblationNoTransferCost(QueueAwareNSGA2Policy):
    def __init__(self, **kwargs):
        super().__init__(queue_aware=True, transfer_accounting=False, **kwargs)
