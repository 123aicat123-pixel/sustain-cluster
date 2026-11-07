"""Minimal reproducible planner latency aggregation (not simulator wall time)."""

import math


def summarize_dispatch_latency(seconds, batch_sizes):
    """Nearest-rank p50/p95 across nonempty decision batches.

    Metrics are descriptive hardware-dependent wall-clock readings. The
    per-task mean divides summed decision time by total batch task count,
    rather than averaging per-batch ratios.
    """
    if len(seconds) != len(batch_sizes):
        raise ValueError("duration and batch count lengths must match")
    if any(not isinstance(n, int) or isinstance(n, bool) or n <= 0
           for n in batch_sizes):
        raise ValueError("all timed batches must be nonempty")
    if any(not math.isfinite(x) or x < 0 for x in seconds):
        raise ValueError("durations must be finite and nonnegative")
    count = len(seconds)
    tasks = sum(batch_sizes)
    if not count:
        return {
            "planner_dispatch_calls": 0,
            "planner_dispatched_tasks": 0,
            "planner_dispatch_seconds": 0.0,
            "planner_dispatch_mean_ms": None,
            "planner_dispatch_p50_ms": None,
            "planner_dispatch_p95_ms": None,
            "planner_dispatch_max_ms": 0.0,
            "planner_dispatch_ms_per_task": None,
        }
    ordered = sorted(seconds)
    percentile = lambda q: 1000 * ordered[math.ceil(q * count) - 1]
    total = sum(seconds)
    return {
        "planner_dispatch_calls": count,
        "planner_dispatched_tasks": tasks,
        "planner_dispatch_seconds": total,
        "planner_dispatch_mean_ms": 1000 * total / count,
        "planner_dispatch_p50_ms": percentile(0.50),
        "planner_dispatch_p95_ms": percentile(0.95),
        "planner_dispatch_max_ms": 1000 * ordered[-1],
        "planner_dispatch_ms_per_task": 1000 * total / tasks,
    }
