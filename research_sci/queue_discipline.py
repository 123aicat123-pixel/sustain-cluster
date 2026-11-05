"""Opt-in, in-simulator queue discipline for controlled ablation.

The actual SustainDC pending_tasks deque is reordered immediately BEFORE
its ordinary dc.step processes arrivals. TaskSchedulingEnv.step has already
moved arrived in-transit jobs into that deque, so the intervention includes
new arrivals and existing pending work. No arrivals, routing actions,
resource availability, future task properties or actual completion
times are altered here.

EDF is a standard queue scheduling baseline, not a new algorithm.
FIFO remains the unmodified default. Installing twice is forbidden.
"""
from collections import deque
from types import MethodType

VALID_QUEUE_ORDERS = ("fifo", "edf")


def priority_key(task):
    """Predecision earliest absolute SLA deadline, deterministic tie-break."""
    deadline = getattr(task, "sla_deadline", None)
    if deadline is None:
        raise ValueError("EDF requires an explicit task SLA deadline")
    return (deadline, float(task.duration), str(task.job_name))


def sort_pending_queue(dc, queue_order):
    if queue_order not in VALID_QUEUE_ORDERS:
        raise ValueError("Unknown queue discipline")
    if queue_order == "fifo":
        return
    if not isinstance(dc.pending_tasks, deque):
        raise TypeError("Expected original datacenter pending queue to be deque")
    tasks = sorted(dc.pending_tasks, key=priority_key)
    dc.pending_tasks.clear()
    dc.pending_tasks.extend(tasks)


def install_queue_discipline(datacenters, queue_order):
    if queue_order not in VALID_QUEUE_ORDERS:
        raise ValueError("Unknown queue discipline")
    if queue_order == "fifo":
        return
    for dc in datacenters.values():
        if getattr(dc, "_research_queue_discipline", None) is not None:
            raise AssertionError("Queue discipline already installed")
        original_step = dc.step
        def wrapped_step(self, action_dict, logger, _original=original_step):
            sort_pending_queue(self, queue_order)
            return _original(action_dict, logger)
        dc.step = MethodType(wrapped_step, dc)
        dc._research_queue_discipline = queue_order
