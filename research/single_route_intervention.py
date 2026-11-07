"""Deterministic, one-time, observable-state route perturbation contracts.

These are controlled simulator interventions, not online policy proposals.
All task choices and destination rankings use currently admitted tasks,
total resource capacities, and current carbon intensity only.
"""
from __future__ import annotations

import math


ARMS=("control","low_ci","high_ci")


def first_batch_probe(tasks, actions, dcs, *, arm):
    """Return (modified_actions, metadata) or (actions, None) if ineligible.

    Precondition: actions and dcs are the SAME 1-based action convention
    as the unified simulator adapter. Called at most once per run, only
    in the first nonempty batch. The original is never mutated.
    """
    if arm not in ARMS:
        raise ValueError("unknown intervention arm")
    if len(tasks)!=len(actions):
        raise AssertionError("tasks/actions misaligned")
    if not tasks:
        return list(actions),None
    if len(dcs)<2 or not all(1<=a<=len(dcs) for a in actions):
        raise AssertionError("invalid action/DC lattice")
    priority=sorted(range(len(tasks)),key=lambda i:(
        -float(tasks[i].cores_req)*float(tasks[i].duration),i))
    for ix in priority:
        task=tasks[ix]
        action=actions[ix]
        candidates=[]
        for j,dc in enumerate(dcs):
            if j+1 == action:
                continue
            if not (task.cores_req<=dc.total_cores and
                    task.gpu_req<=dc.total_gpus and
                    task.mem_req<=dc.total_mem_GB):
                continue
            ci=float(dc.get_current_carbon_intensity(norm=False))
            if not math.isfinite(ci) or ci<0:
                raise ValueError("invalid observed carbon intensity")
            candidates.append((ci,int(dc.dc_id),j+1))
        if not candidates:
            continue
        chosen=(min(candidates,key=lambda x:(x[0],x[1])) if arm=="low_ci"
                else max(candidates,key=lambda x:(x[0],-x[1])))
        selected=action if arm=="control" else chosen[2]
        result=list(actions)
        result[ix]=selected
        meta={"task_index":ix,"task_name":str(task.job_name),
              "origin_dc_id":int(task.origin_dc_id),
              "control_dc_id":int(dcs[action-1].dc_id),
              "selected_dc_id":int(dcs[selected-1].dc_id),
              "alternative_dc_id":int(dcs[chosen[2]-1].dc_id),
              "original_action":action,"chosen_action":selected,
              "original_cpu_cores":float(task.cores_req),
              "duration_minutes":float(task.duration),
              "observed_selected_ci":float(dcs[selected-1].get_current_carbon_intensity(norm=False)),
              "observed_alternative_ci":chosen[0],
              "arm":arm}
        if arm!="control" and selected==action:
            raise AssertionError("intervention must alter the chosen route")
        if sum(a!=b for a,b in zip(actions,result))!=int(arm!="control"):
            raise AssertionError("more than one action changed")
        return result,meta
    return list(actions),None
