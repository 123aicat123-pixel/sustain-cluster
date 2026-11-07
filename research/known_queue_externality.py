"""Known-queue counterfactual delay probe for online research diagnostics.

Replays ONLY currently observed running tasks, pending FIFO tasks and
already committed in-transit arrivals. The added hypothetical batch is
the sole intervention. Future workload admissions are never used.

This is a computational predictor, NOT causal identification of realized
task outcomes, a deadline guarantee, or physically calibrated carbon.
"""
from __future__ import annotations

from collections import deque
from datetime import timedelta

STEP = timedelta(minutes=15)


def project_tracked_starts(dc, arrivals, now, *, tracked=(), max_steps=672):
    """Predict start for tracked known queued/transit and new tasks.

    Arrivals are (task, eligible_time) pairs. Already pending tasks appear
    first at equal tick, matching the existing research FIFO approximation.
    """
    arriving = [t for t, _ in arrivals]
    pending = list(dc.pending_tasks)
    tracked = tuple(tracked)
    all_objects = pending + arriving
    if len({id(t) for t in all_objects}) != len(all_objects):
        raise AssertionError("duplicate task identity in queue projection")
    if any(t not in all_objects for t in tracked):
        raise AssertionError("tracked task absent from observable queue")
    track_ids = {id(t) for t in tracked + tuple(arriving)}
    limits = (float(dc.total_cores), float(dc.total_gpus),
              float(dc.total_mem_GB))
    available = [float(dc.available_cores), float(dc.available_gpus),
                 float(dc.available_mem)]
    def resources(task):
        return (float(task.cores_req), float(task.gpu_req), float(task.mem_req))
    if any(any(x > limit + 1e-8 for x, limit in
               zip(resources(t), limits)) for t in all_objects):
        raise ValueError("known task exceeds total capacity")
    running = [(t.finish_time, t) for t in dc.running_tasks]
    if any(when is None for when, _ in running):
        raise ValueError("running task missing finish time")
    waiting = sorted(enumerate(arrivals), key=lambda x: (x[1][1], x[0]))
    queue = deque(pending)
    starts = {}
    cursor = 0
    if not track_ids:
        return {}
    for tick_number in range(max_steps + 1):
        tick = now + STEP * tick_number
        still_running = []
        for finish, task in running:
            if finish <= tick:
                available = [a + needed for a, needed in
                             zip(available, resources(task))]
            else:
                still_running.append((finish, task))
        running = still_running
        while cursor < len(waiting) and waiting[cursor][1][1] <= tick:
            queue.append(waiting[cursor][1][0])
            cursor += 1
        for _ in range(len(queue)):
            task = queue.popleft()
            needed = resources(task)
            if all(a + 1e-8 >= n for a, n in zip(available, needed)):
                available = [a - n for a, n in zip(available, needed)]
                running.append((tick + timedelta(minutes=float(task.duration)), task))
                if id(task) in track_ids:
                    starts[task] = tick
            else:
                queue.append(task)
        if len(starts) == len(track_ids):
            return starts
    raise RuntimeError("tracked queue prediction exhausted")


def known_queue_externality(dc, new_arrivals, now, pending_transit=()):
    """Compare known-task predicted start under no dispatch vs hypothetical batch.

    The same currently committed transit arrivals are included in both arms.
    Returns delay and additional *predicted* tardiness on PREEXISTING jobs.
    """
    existing_pending = tuple(dc.pending_tasks)
    transit = [(task, max(now, eta)) for eta, task in pending_transit]
    existing = existing_pending + tuple(task for task, _ in transit)
    if len({id(t) for t in existing}) != len(existing):
        raise AssertionError("duplicate committed queue task")
    no_action = project_tracked_starts(
        dc, transit, now, tracked=existing_pending)
    with_action = project_tracked_starts(
        dc, transit + list(new_arrivals), now, tracked=existing_pending)
    total_delay = total_added_tardiness = 0.0
    delayed = 0
    for task in existing:
        earlier, later = no_action[task], with_action[task]
        delta = (later-earlier).total_seconds() / 60
        if delta < -1e-8:
            raise AssertionError("new arrivals advanced a committed task")
        total_delay += max(0.0, delta)
        delayed += int(delta > 1e-8)
        finish0 = earlier + timedelta(minutes=float(task.duration))
        finish1 = later + timedelta(minutes=float(task.duration))
        tard0 = max(0.0, (finish0-task.sla_deadline).total_seconds()/60)
        tard1 = max(0.0, (finish1-task.sla_deadline).total_seconds()/60)
        total_added_tardiness += max(0.0, tard1-tard0)
    return {
        "known_committed_tasks": len(existing),
        "known_tasks_delayed": delayed,
        "known_added_wait_minutes": total_delay,
        "known_added_tardiness_minutes": total_added_tardiness,
        "new_tasks_in_hypothesis": len(new_arrivals),
    }
