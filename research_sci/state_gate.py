"""Predeclared observational gate for activating bounded batch planning.

Use ONLY currently observable running/pending jobs, known in-transit
commitments, current batch demands, network delays and deadline
timestamps. The decision never reads completed task outcomes, future
arrivals, future grid emissions or results from later heldout periods.

Fixed rule before September/October transfer evaluation:
  - at least 2 jobs in the visible batch
  - at least 50% of jobs have SOME optimistic, unbuffered SLA-feasible
    center under the current known FIFO queue state.
When the estimated feasible action set is very sparse, retain the
original commitment-aware per-task greedy baseline. This hypothesis
was motivated by August exploratory results; September and October
are genuinely different calendar workload slices but remain a
single public workload source. This is a heuristic, not a learned
chance-constraint or SLA guarantee.
"""
import math
from research_sci.queue_risk import predict_finish


class FeasibleCoverageGate:
    def __init__(self, threshold=0.5, min_batch_size=2, delay_fn=None):
        if not math.isfinite(threshold) or not (0 < threshold <= 1):
            raise ValueError("threshold must be in (0,1]")
        if type(min_batch_size) is not int or min_batch_size < 2:
            raise ValueError("At least two tasks required for joint lookahead")
        if delay_fn is None:
            from data.network_cost.network_delay import get_transmission_delay
            delay_fn=get_transmission_delay
        self.threshold=float(threshold)
        self.min_batch_size=min_batch_size
        self.delay_fn=delay_fn

    def assess(self, tasks,datacenters,now,manager,known_by_dc,
               step_seconds=900):
        if type(step_seconds) is not int or step_seconds <= 0:
            raise ValueError("step_seconds must be positive integer")
        if len(set(map(id,tasks)))!=len(tasks):
            raise AssertionError("Repeated task objects in visible batch")
        centers=sorted(datacenters.values(),key=lambda dc:dc.dc_id)
        if not centers:
            raise ValueError("No datacenters")
        feasible=0
        forecastable=0
        for task in tasks:
            origin=manager.get_dc_location(task.origin_dc_id)
            has_feasible=False
            has_forecast=False
            for dc in centers:
                delay=float(self.delay_fn(
                    origin,dc.location,manager.cloud_provider,
                    task.bandwidth_gb
                ))
                if not math.isfinite(delay) or delay < 0:
                    raise ValueError("Invalid transfer delay")
                ticks=max(1,math.ceil(delay/step_seconds))
                finish=predict_finish(
                    task,dc,now,ticks,step_seconds=step_seconds,
                    known_arrivals=known_by_dc.get(dc.dc_id,()),
                    queue_order="fifo"
                )
                if finish is not None:
                    has_forecast=True
                    if finish <= task.sla_deadline:
                        has_feasible=True
                        break
            forecastable+=int(has_forecast)
            feasible+=int(has_feasible)
        ratio=feasible/len(tasks) if tasks else 0.
        return {
            "tasks":len(tasks),"feasible_tasks":feasible,
            "forecastable_tasks_at_least_one_checked":forecastable,
            "feasible_fraction":ratio,
            "activate":(
                len(tasks)>=self.min_batch_size and ratio>=self.threshold
            ),
            "threshold":self.threshold,
        }
