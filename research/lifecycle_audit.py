"""Strict accounting of task lifecycle states in a research simulation.

This code is independent of the simulator's energy model, and accepts objects
as task identifiers. Never use `id(task)` as the only persistent identifier:
Python may recycle IDs when objects are garbage collected.
"""


def audit_lifecycle(dispatched, finished, pending, running, in_transit):
    """Return exact counts; raise on missing/duplicated task ownership.

    All arguments are collections of task objects. The simulator has no
    cancellation operation in this evaluation mode, so every dispatched task
    must be either finished, pending, running, or in transit.
    """
    all_dispatch = set(dispatched)
    states = {
        "finished": list(finished),
        "pending": list(pending),
        "running": list(running),
        "in_transit": list(in_transit),
    }
    owner = {}
    for state, tasks in states.items():
        if len(tasks) != len(set(tasks)):
            raise AssertionError(f"Repeated task in {state}")
        for task in tasks:
            if task not in all_dispatch:
                raise AssertionError(f"Unknown task found in {state}")
            if task in owner:
                raise AssertionError(f"Task appears in {owner[task]} and {state}")
            owner[task] = state
    missing = all_dispatch - set(owner)
    if missing:
        raise AssertionError(f"{len(missing)} dispatched tasks missing from lifecycle")
    return {
        "finished": len(states["finished"]),
        "pending": len(states["pending"]),
        "running": len(states["running"]),
        "in_transit": len(states["in_transit"]),
        "dispatched": len(all_dispatch),
        "unfinished": len(all_dispatch - set(finished)),
    }
