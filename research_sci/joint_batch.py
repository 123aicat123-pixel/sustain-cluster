"""Bounded joint batch-assignment baseline with explicit task reservations.

A beam search enumerates placements for the *currently visible* batch,
in the same order TaskSchedulingEnv.step will commit its task actions.
Every branch carries its OWN existing/in-transit and earlier-batch
reservations. The model estimates FIFO 15-minute scheduling with the
same predict_finish as the original queue-aware baseline.

Predeclared, deterministic lexicographic objective:
  1. Fewest optimistically predicted deadline misses.
  2. Least total optimistic lateness among jobs predicted late.
  3. Fewest jobs missing the conservative risk buffer.
  4. Smallest work-weighted CURRENT grid-carbon intensity proxy.
No measured facility or network carbon is used in the route score.
Beam width=4 and chunk_size=8 bound the combinatorial search; choices
are NOT guaranteed global optimum. The current clock and currently
visible batch/queues only. No future arrivals, hidden carbon or actual
completion labels are read. This is a research baseline, NOT safe RL.
"""
from datetime import timedelta
import math

from research_sci.queue_risk import predict_finish


class JointBatchCarbonPlanner:
    def __init__(self, risk_buffer_minutes=30, beam_width=4,
                 chunk_size=8, delay_fn=None):
        if not math.isfinite(risk_buffer_minutes) or risk_buffer_minutes < 0:
            raise ValueError("Invalid risk buffer")
        if type(beam_width) is not int or beam_width < 1:
            raise ValueError("beam_width must be a positive integer")
        if type(chunk_size) is not int or chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer")
        if delay_fn is None:
            from data.network_cost.network_delay import get_transmission_delay
            delay_fn = get_transmission_delay
        self.buffer_minutes = float(risk_buffer_minutes)
        self.beam_width = beam_width
        self.chunk_size = chunk_size
        self.delay_fn = delay_fn

    @staticmethod
    def _carbon_proxy(dc, task, intensity):
        # Only predecision workload/intensity, NOT the actual facility energy.
        cpu = float(task.cores_req)/max(float(dc.total_cores),1.)
        gpu = float(task.gpu_req)/max(float(dc.total_gpus),1.)
        mem = float(task.mem_req)/max(float(dc.total_mem_GB),1.)
        duration = float(task.duration)
        if any(not math.isfinite(x) or x < 0 for x in (cpu,gpu,mem,duration)):
            raise ValueError("Invalid task demand or duration")
        return intensity*duration*(cpu+gpu+mem)

    def plan(self, tasks, datacenters, now, manager, known_by_dc,
             step_seconds=900):
        if type(step_seconds) is not int or step_seconds <= 0:
            raise ValueError("step_seconds must be a positive integer")
        if len({id(t) for t in tasks}) != len(tasks):
            raise AssertionError("Repeated task objects in current batch")
        dcs = sorted(datacenters.values(),key=lambda x:x.dc_id)
        if not dcs:
            raise ValueError("No datacenters")
        by_id = {dc.dc_id:dc for dc in dcs}
        if len(by_id) != len(dcs):
            raise ValueError("Duplicate datacenter IDs")

        base = {dc.dc_id:list(known_by_dc.get(dc.dc_id,())) for dc in dcs}
        base_tick = timedelta(seconds=step_seconds)
        routes, predictions = [], []
        chunks, expansions = 0, 0
        # Cache per-step known network delays / intensities. The physical
        # datacenter resources do not change inside a batch before env.step.
        cache = {}
        for task in tasks:
            origin=manager.get_dc_location(task.origin_dc_id)
            choices=[]
            for dc in dcs:
                delay=float(self.delay_fn(origin,dc.location,
                                          manager.cloud_provider,
                                          task.bandwidth_gb))
                intensity=float(dc.get_current_carbon_intensity(norm=False))
                if (not math.isfinite(delay) or delay < 0 or
                    not math.isfinite(intensity) or intensity < 0):
                    raise ValueError("Invalid observed transfer delay/carbon intensity")
                ticks=max(1,math.ceil(delay/step_seconds))
                eta=max(now+base_tick,now+timedelta(seconds=delay))
                choices.append((
                    dc.dc_id,dc,ticks,eta,
                    self._carbon_proxy(dc,task,intensity)
                ))
            cache[task]=choices

        for start in range(0,len(tasks),self.chunk_size):
            chunks+=1
            current=tasks[start:start+self.chunk_size]
            # State: (4-component score, route tuple, finish tuple, branch
            # commitments). Prefix score is a pruning heuristic, not exact
            # future total outcome optimization.
            frontier=[((0,0.,0,0.),(),(),base)]
            for task in current:
                expanded=[]
                for score,chosen,finishes,commitments in frontier:
                    candidates=[]
                    for dc_id,dc,ticks,eta,proxy in cache[task]:
                        forecast=predict_finish(
                            task,dc,now,ticks,step_seconds=step_seconds,
                            known_arrivals=commitments[dc_id],
                            queue_order="fifo"
                        )
                        if forecast is None:
                            miss,buffer_miss,late=1,1,2880.
                        else:
                            slack=(task.sla_deadline-forecast).total_seconds()/60
                            miss=int(slack < 0)
                            buffer_miss=int(slack < self.buffer_minutes)
                            late=max(0.,-slack)
                        candidate_score=(
                            score[0]+miss,
                            score[1]+late,
                            score[2]+buffer_miss,
                            score[3]+proxy
                        )
                        candidates.append((candidate_score,dc_id,forecast,eta))
                        expansions+=1
                    # When none is forecastable, maintain the same explicit
                    # origin-DC fallback as the queue-aware greedy baseline.
                    if all(pred is None for _,_,pred,_ in candidates):
                        origin_choice=next(
                            (c for c in candidates if c[1]==task.origin_dc_id),
                            min(candidates,key=lambda c:c[1])
                        )
                        candidates=[origin_choice]
                    for next_score,dc_id,forecast,eta in candidates:
                        next_commitments=dict(commitments)
                        next_commitments[dc_id]=commitments[dc_id]+[(eta,task)]
                        expanded.append((
                            next_score,chosen+(dc_id,),
                            finishes+(forecast,),next_commitments
                        ))
                # The routes tie-break makes runs deterministic and permits
                # seed-paired replay without synthetic randomness.
                expanded.sort(key=lambda x:(x[0],x[1]))
                frontier=expanded[:self.beam_width]
            best=frontier[0]
            routes.extend(best[1])
            predictions.extend(best[2])
            base=best[3]

        if len(routes)!=len(tasks) or len(predictions)!=len(tasks):
            raise AssertionError("Incomplete visible-batch plan")
        return {
            "routes":routes,"predictions":predictions,
            "chunks":chunks,"expansions":expansions,
            "beam_width":self.beam_width,"chunk_size":self.chunk_size,
        }
