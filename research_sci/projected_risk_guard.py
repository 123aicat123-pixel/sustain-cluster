"""Same-state projected-SLA safeguard for bounded joint routing.

Evaluate the *entire currently visible batch* twice before any actions
are committed to the real simulator: a shadow task-by-task greedy route
and a candidate 4x8-beam route. Both use the SAME observed data center
capacities, running/pending queues and known in-transit tasks. Each
rollout carries its own earlier same-batch commitments.

Guard0: accept beam only if NO task's optimistic completion forecast is
later than that task's greedy forecast, and some projected finish or
work-weighted instantaneous carbon proxy strictly improves.
Guard15: jobs that were predicted >=30 min buffered-safe under greedy
may be postponed by at most 15 minutes *without crossing the original
30-minute buffered-safety boundary*. All other jobs must not be later.

Neither guard is a formal risk guarantee. Both ignore unknown future
arrivals, imprecise release times and future weather/carbon. Guard15
is more permissive, but its buffer-preserving limit is fixed here
before November/December evaluation. Unknown forecast is *worse* than
any known forecast, and unknown-vs-unknown is not evidence of gain.
"""
from datetime import timedelta
import math

from research_sci.joint_batch import JointBatchCarbonPlanner
from research_sci.queue_risk import QueueRiskCarbonPolicy, predict_finish


class ProjectedRiskGuard:
    NAMES = ("guard0", "guard15")

    def __init__(self, name, risk_buffer_minutes=30, delay_fn=None):
        if name not in self.NAMES:
            raise ValueError("Unrecognized projected-risk guard")
        if not math.isfinite(risk_buffer_minutes) or risk_buffer_minutes < 0:
            raise ValueError("Risk buffer must be finite and nonnegative")
        if delay_fn is None:
            from data.network_cost.network_delay import get_transmission_delay
            delay_fn = get_transmission_delay
        self.name=name
        self.buffer_minutes=float(risk_buffer_minutes)
        self.delay_fn=delay_fn

    def _shadow_greedy(self, tasks, dcs, now, manager, known_by_dc,
                       step_seconds):
        ordered=sorted(dcs.values(),key=lambda x:x.dc_id)
        by_id={dc.dc_id:dc for dc in ordered}
        if len(ordered)!=len(by_id):
            raise ValueError("Duplicate DC IDs")
        reservations={dc_id:list(known_by_dc.get(dc_id,()))
                      for dc_id in by_id}
        policy=QueueRiskCarbonPolicy(
            "queue_risk_carbon",risk_buffer_minutes=self.buffer_minutes,
            delay_fn=self.delay_fn,queue_order="fifo"
        )
        interval=timedelta(seconds=step_seconds)
        routes=[]
        predicted=[]
        proxy=0.
        for task in tasks:
            if now > task.sla_deadline:
                # The upstream simulator forcibly sends expired jobs to
                # origin with zero transfer wait. Both candidate plans
                # must be rejected in such a batch (see review).
                route=task.origin_dc_id
                forecast=None
                eta=now
            else:
                policy.set_visible_commitments(reservations)
                route,_=policy.choose(
                    task,dcs,now,manager,step_seconds=step_seconds
                )
                if route not in by_id:
                    raise AssertionError("Shadow greedy chose unknown center")
                dc=by_id[route]
                origin=manager.get_dc_location(task.origin_dc_id)
                delay=float(self.delay_fn(
                    origin,dc.location,manager.cloud_provider,
                    task.bandwidth_gb
                ))
                if not math.isfinite(delay) or delay < 0:
                    raise ValueError("Invalid observed network delay")
                ticks=max(1,math.ceil(delay/step_seconds))
                forecast=predict_finish(
                    task,dc,now,ticks,step_seconds=step_seconds,
                    known_arrivals=reservations[route],queue_order="fifo"
                )
                if forecast != policy.dispatch_prediction_by_task[task]:
                    raise AssertionError("Shadow greedy forecast mismatch")
                eta=max(now+interval,now+timedelta(seconds=delay))
            if route not in by_id:
                raise AssertionError("Unknown forced origin DC")
            dc=by_id[route]
            carbon=float(dc.get_current_carbon_intensity(norm=False))
            if not math.isfinite(carbon) or carbon < 0:
                raise ValueError("Invalid observed carbon intensity")
            proxy+=JointBatchCarbonPlanner._carbon_proxy(dc,task,carbon)
            reservations[route].append((eta,task))
            routes.append(route)
            predicted.append(forecast)
        return {"routes":routes,"predictions":predicted,"carbon_proxy":proxy}

    def review(self, tasks,dcs,now,manager,known_by_dc,beam_result,
               step_seconds=900):
        if type(step_seconds) is not int or step_seconds <= 0:
            raise ValueError("Time-step must be a positive integer")
        if len({id(t) for t in tasks})!=len(tasks):
            raise AssertionError("Repeated task objects in batch")
        if len(beam_result["routes"])!=len(tasks) or len(
            beam_result["predictions"]
        )!=len(tasks):
            raise AssertionError("Incomplete beam batch proposal")
        if not tasks or any(now > t.sla_deadline for t in tasks):
            # Do not consider the forward-model forecast for tasks whose
            # routing will be overridden by the environment.
            return {
                "accepted":False,"reason":"empty_or_forced_origin",
                "greedy_routes":None,"greedy_predictions":None,
                "greedy_carbon_proxy":None,"beam_carbon_proxy":None,
                "predicted_late_greedy":None,"predicted_late_beam":None
            }
        base=self._shadow_greedy(tasks,dcs,now,manager,known_by_dc,
                                 step_seconds)
        by_id={dc.dc_id:dc for dc in dcs.values()}
        if len(by_id)!=len(dcs):
            raise ValueError("Duplicate datacenter IDs")
        proxy=0.
        safe=True
        strict_finish_better=False
        predicted_late_base=0
        predicted_late_beam=0
        buffered_base=0
        buffered_beam=0
        tolerance=0. if self.name=="guard0" else 15.
        for task,dc_id,finish,reference in zip(
            tasks,beam_result["routes"],beam_result["predictions"],
            base["predictions"]
        ):
            if dc_id not in by_id:
                raise ValueError("Beam chose unknown datacenter ID")
            dc=by_id[dc_id]
            intensity=float(dc.get_current_carbon_intensity(norm=False))
            if not math.isfinite(intensity) or intensity < 0:
                raise ValueError("Invalid observed carbon intensity")
            proxy+=JointBatchCarbonPlanner._carbon_proxy(dc,task,intensity)
            if reference is None:
                predicted_late_base+=1
                buffered_base+=1
                predicted_late_beam+=int(finish is None or finish>task.sla_deadline)
                buffered_beam+=int(
                    finish is None or
                    (task.sla_deadline-finish).total_seconds()/60.<self.buffer_minutes
                )
                if finish is not None:
                    strict_finish_better=True
                # A still-missing forecast is not a positive result.
                continue
            base_slack=(task.sla_deadline-reference).total_seconds()/60.
            predicted_late_base+=int(base_slack<0)
            buffered_base+=int(base_slack<self.buffer_minutes)
            if finish is None:
                predicted_late_beam+=1
                buffered_beam+=1
                safe=False
                continue
            new_slack=(task.sla_deadline-finish).total_seconds()/60.
            predicted_late_beam+=int(new_slack<0)
            buffered_beam+=int(new_slack<self.buffer_minutes)
            if finish<reference:
                strict_finish_better=True
            permitted=tolerance if base_slack>=self.buffer_minutes else 0.
            # This never consumes the original buffered-safety reserve.
            permitted=min(permitted,max(0.,base_slack-self.buffer_minutes))
            if (finish-reference).total_seconds()/60. > permitted+1e-9:
                safe=False
        if predicted_late_beam>predicted_late_base or buffered_beam>buffered_base:
            safe=False
        if not safe:
            reason="forecast_sla_regression"
            accepted=False
        elif not (strict_finish_better or proxy<base["carbon_proxy"]-1e-9):
            reason="no_strict_projected_gain"
            accepted=False
        else:
            reason="projected_pareto_accepted"
            accepted=True
        return {
            "accepted":accepted,"reason":reason,
            "greedy_routes":base["routes"],
            "greedy_predictions":base["predictions"],
            "greedy_carbon_proxy":base["carbon_proxy"],
            "beam_carbon_proxy":proxy,
            "predicted_late_greedy":predicted_late_base,
            "predicted_late_beam":predicted_late_beam,
            "predicted_buffer_shortfalls_greedy":buffered_base,
            "predicted_buffer_shortfalls_beam":buffered_beam,
            "projected_carbon_proxy_delta":proxy-base["carbon_proxy"],
        }
