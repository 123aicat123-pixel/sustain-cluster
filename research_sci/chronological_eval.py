"""Chronologically separated, frozen-risk holdout evaluation.

One simulator clock, and three non-overlapping arrival intervals:
  calibration admissions -> admission-free drain -> held-out admissions
  -> held-out drain.

Both treatments share the SAME seed, calibration policy and calibration
workload, then differ ONLY in fixed risk buffer vs pre-test frozen empirical
error quantile. The risk buffer is frozen before any held-out admissions.
No forecast ground truth, test completion labels or test data informs it.
"""
import argparse
import copy
import csv
import hashlib
import json
import math
import random
import tempfile
from datetime import date, timedelta
from pathlib import Path

from research_sci.online_calibration import OnlineResidualCalibrator
from research_sci.prediction_audit import summarize_forecasts
from research_sci.queue_risk import QueueRiskCarbonPolicy, predict_finish
from research_sci.state_risk_audit import snapshot_decision, audit_state_risk
from research_sci.action_feasibility_audit import evaluate_candidates, summarize_candidate_audit
from research_sci.queue_discipline import VALID_QUEUE_ORDERS, install_queue_discipline
from research_sci.joint_batch import JointBatchCarbonPlanner
from research_sci.state_gate import FeasibleCoverageGate
from research_sci.projected_risk_guard import ProjectedRiskGuard

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/env/sim_config.yaml"
DC_CONFIG = ROOT / "configs/env/datacenters.yaml"
REWARD_CONFIG = ROOT / "configs/env/reward_config.yaml"


TREATMENTS = ("fixed_30", "fixed_60", "fixed_120", "precalibrated_frozen")


def frozen_buffer_for_treatment(treatment, learned_minutes):
    """A priori fixed-margin controls plus margin learned before test begins.

    This is a heuristic buffer sweep, not a certified probabilistic risk budget.
    """
    if treatment not in TREATMENTS:
        raise ValueError(f"Unknown treatment {treatment}")
    if not math.isfinite(learned_minutes) or learned_minutes < 0:
        raise ValueError("Invalid historical risk margin")
    if treatment == "precalibrated_frozen":
        return float(learned_minutes)
    return float(treatment.split("_")[1])



def timeline_phase(index, calibration_steps, gap_steps, test_steps, drain_steps):
    if min(calibration_steps, gap_steps, test_steps, drain_steps) < 1:
        raise ValueError("All phase lengths must be positive")
    if index < 0 or index >= calibration_steps + gap_steps + test_steps + drain_steps:
        raise ValueError("Step outside experiment timeline")
    if index < calibration_steps:
        return "calibration"
    if index < calibration_steps + gap_steps:
        return "calibration_drain"
    if index < calibration_steps + gap_steps + test_steps:
        return "heldout"
    return "heldout_drain"


def _signature(items):
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode("utf-8")).hexdigest()


def finished_work_signature(tasks):
    """Compare actual completed task identities and requirements, not counts.

    Same number of completed jobs can hide different jobs / total compute.
    Match a sorted multiset of stable task attributes, independent of
    Python object identity or completion order.
    """
    records = sorted(
        (
            str(task.job_name),
            task.arrival_time.isoformat(),
            float(task.duration),
            float(task.cores_req),
            float(task.gpu_req),
            float(task.mem_req),
        )
        for task in tasks
    )
    return _signature(records)


def _create_env(seed, total_steps, capacity_scale, scratch,
                sim_duration_days=None, calendar_month=None, calendar_day=None):
    # Defer simulator and ML dependency imports: lightweight contract tests
    # run on GitHub Actions without installing 3rd-party packages.
    import numpy as np
    import yaml
    from train_SAC_agent import make_env

    if not (0 < capacity_scale <= 1):
        raise ValueError("capacity_scale must lie in (0, 1]")
    required_days = math.ceil((total_steps + 1) / 96)
    if sim_duration_days is not None and (
        not isinstance(sim_duration_days, int)
        or sim_duration_days < required_days or sim_duration_days > 7
    ):
        raise ValueError("Fixed simulator duration must cover the entire experiment")
    random.seed(seed)
    np.random.seed(seed)
    config = copy.deepcopy(yaml.safe_load(CONFIG.read_text(encoding="utf-8")))
    sim = config["simulation"]
    if (calendar_month is None) != (calendar_day is None):
        raise ValueError("Calendar month and day must be provided together")
    if calendar_month is not None:
        if (type(calendar_month) is not int or type(calendar_day) is not int):
            raise ValueError("Calendar month and day must be integer")
        # Validate the real calendar before loading the corresponding 2020
        # Alibaba workload and year-2023 environmental time sequence.
        date(int(sim["year"]), calendar_month, calendar_day)
        date(2020, calendar_month, calendar_day)
        sim["month"] = calendar_month
        sim["init_day"] = calendar_day
    sim.update({
        "strategy": "manual_rl",
        "single_action_mode": False,
        "disable_defer_action": False,
        "shuffle_datacenters": False,
        "use_tensorboard": False,
        "duration_days": (sim_duration_days if sim_duration_days is not None
                          else max(4, required_days)),
    })
    cfg_path = scratch / "simulation.yaml"
    cfg_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    dc_path = DC_CONFIG
    if capacity_scale < 1:
        dc_config = copy.deepcopy(yaml.safe_load(DC_CONFIG.read_text(encoding="utf-8")))
        for dc in dc_config["datacenters"]:
            for key in ("total_cores", "total_gpus", "total_mem"):
                dc[key] = max(1, int(dc[key] * capacity_scale))
        dc_path = scratch / "datacenters.yaml"
        dc_path.write_text(yaml.safe_dump(dc_config), encoding="utf-8")
    env = make_env(str(cfg_path), str(dc_path), str(REWARD_CONFIG),
                   writer=None, logger=None)
    if env.single_action_mode or env.disable_defer_action:
        raise AssertionError("Matched per-task action route is required")
    return env


def run_one(seed, treatment, calibration_steps=16, gap_steps=128,
            test_steps=16, drain_steps=96, capacity_scale=0.02,
            alpha=0.1, min_samples=20, sim_duration_days=None,
            audit_states=False, state_audit_dir=None,
            audit_candidates=False, candidate_audit_dir=None,
            heldout_queue_order="fifo", heldout_forecast_order=None,
            heldout_batch_planner="greedy",
            calendar_month=None, calendar_day=None,
            fixed_policy_without_calibration=False):
    if treatment not in TREATMENTS:
        raise ValueError(f"Unknown treatment {treatment}")
    if heldout_queue_order not in VALID_QUEUE_ORDERS:
        raise ValueError("Unsupported heldout queue discipline")
    if heldout_forecast_order is None:
        heldout_forecast_order = heldout_queue_order
    if heldout_forecast_order not in VALID_QUEUE_ORDERS:
        raise ValueError("Unsupported forecast queue discipline")
    if fixed_policy_without_calibration and treatment != "fixed_30":
        raise ValueError(
            "No-calibration calendar transfer is permitted ONLY for the "
            "predeclared fixed_30 policy; calibration-dependent policies "
            "must retain their training arrivals"
        )
    if heldout_batch_planner not in ("greedy","beam4","gate50","guard0","guard15"):
        raise ValueError("Unsupported heldout batch planner")
    if heldout_batch_planner in ("beam4","gate50","guard0","guard15") and (
        heldout_queue_order != "fifo" or heldout_forecast_order != "fifo"
    ):
        raise ValueError("Joint batch baseline requires matched FIFO execution/forecast")
    total_steps = calibration_steps + gap_steps + test_steps + drain_steps
    # These must fit the chosen fixed 15-minute time grid.
    timeline_phase(total_steps-1, calibration_steps, gap_steps, test_steps, drain_steps)
    if total_steps > 672:
        raise ValueError("Keep pilot within seven-day simulator trace")

    from data.network_cost.network_delay import get_transmission_delay

    with tempfile.TemporaryDirectory(prefix="sci_chronological_") as tmp:
        env = _create_env(seed, total_steps, capacity_scale, Path(tmp),
                          sim_duration_days=sim_duration_days,
                          calendar_month=calendar_month,calendar_day=calendar_day)
        try:
            dt = env.time_step
            t0 = env.start_time
            cal_end = t0 + calibration_steps * dt
            test_start = t0 + (calibration_steps + gap_steps) * dt
            test_end = test_start + test_steps * dt
            original_loader = env.cluster_manager.get_tasks_for_timestep

            def admission_gate(now):
                if ((not fixed_policy_without_calibration and
                     t0 <= now < cal_end) or (test_start <= now < test_end)):
                    return original_loader(now)
                return []

            # Install BEFORE reset so initial admissions cannot bypass gate.
            env.cluster_manager.get_tasks_for_timestep = admission_gate
            env.reset(seed=seed)
            calibrator = OnlineResidualCalibrator(
                alpha=alpha, min_samples=min_samples, fallback_minutes=30,
                window=256,
            )
            training_policy = QueueRiskCarbonPolicy("queue_risk_carbon")
            test_policy = None
            frozen_margin = None
            warmup_tasks = set()
            warmup_finished = set()
            warmup_predictions = {}
            warmup_routes = []
            heldout_tasks = set()
            heldout_finished = set()
            heldout_predictions = {}
            heldout_state_snapshots = {}
            heldout_candidate_snapshots = {}
            heldout_decision_buffers = {}
            heldout_routes = []
            joint_planner = None
            state_gate = None
            risk_guard = None
            metrics = {
                "seed": seed, "treatment": treatment,
                "calendar_month": t0.month, "calendar_day": t0.day,
                "fixed_policy_without_calibration": bool(fixed_policy_without_calibration),
                "queue_discipline": heldout_queue_order,
                "forecast_queue_discipline": heldout_forecast_order,
                "batch_planner": heldout_batch_planner,
                "test_joint_batch_plans": 0,
                "test_joint_beam_expansions": 0,
                "test_joint_chunks": 0,
                "test_gate_batches": 0,
                "test_gate_activated_batches": 0,
                "test_gate_tasks": 0,
                "test_gate_feasible_tasks": 0,
                "test_guard_reviewed_batches": 0,
                "test_guard_accepted_batches": 0,
                "test_guard_rejected_risk": 0,
                "test_guard_rejected_no_gain": 0,
                "test_guard_rejected_forced": 0,
                "test_guard_projected_carbon_delta_accepted": 0.0,
                "capacity_scale": capacity_scale,
                "calibration_steps": calibration_steps, "gap_steps": gap_steps,
                "test_steps": test_steps, "drain_steps": drain_steps,
                "train_window_start": t0.isoformat(),
                "train_admissions_end": cal_end.isoformat(),
                "test_window_start": test_start.isoformat(),
                "test_admissions_end": test_end.isoformat(),
                "test_tasks_admitted": 0, "test_tasks_finished": 0,
                "test_sla_met": 0, "test_sla_violated": 0,
                "test_facility_carbon_kg": 0.0, "test_network_carbon_kg": 0.0,
                "test_facility_cost_usd": 0.0, "test_network_cost_usd": 0.0,
                "test_defer_actions": 0,
            }
            by_id = {dc.dc_id: dc for dc in env.cluster_manager.datacenters.values()}
            index_action = {
                dc.dc_id: i + 1
                for i, dc in enumerate(env.cluster_manager.datacenters.values())
            }

            for step in range(total_steps):
                phase = timeline_phase(step, calibration_steps, gap_steps,
                                       test_steps, drain_steps)
                now = env.current_time
                if phase == "heldout" and test_policy is None:
                    # Require NO train cohort left in running/pending/transit
                    # queues before first test arrival. This is stronger
                    # than merely checking training/test timestamps.
                    if warmup_tasks != warmup_finished:
                        raise AssertionError(
                            f"Calibration queue not drained: "
                            f"{len(warmup_tasks - warmup_finished)} unfinished"
                        )
                    if env.in_transit_tasks or any(
                        dc.pending_tasks or dc.running_tasks for dc in by_id.values()
                    ):
                        raise AssertionError("State not drained before holdout")
                    if fixed_policy_without_calibration:
                        if warmup_tasks or warmup_finished or calibrator.residuals:
                            raise AssertionError(
                                "Explicit trainless fixed-policy transfer "
                                "unexpectedly admitted calibration jobs"
                            )
                    elif len(calibrator.residuals) < min_samples:
                        raise AssertionError("Insufficient observed training residuals")
                    learned = calibrator.margin_minutes()
                    frozen_margin = frozen_buffer_for_treatment(treatment, learned)
                    metrics.update({
                        "pretest_train_completed": len(warmup_finished),
                        "pretest_train_forecast_residuals": calibrator.observed_count,
                        "pretest_learned_buffer_minutes": learned,
                        "applied_frozen_buffer_minutes": frozen_margin,
                        "pretest_calibration_error_p90_minutes": learned,
                        "train_routing_signature": _signature(warmup_routes),
                    })
                    test_policy = QueueRiskCarbonPolicy(
                        "queue_risk_carbon", risk_buffer_minutes=frozen_margin,
                        queue_order=heldout_forecast_order
                    )
                    if heldout_batch_planner in ("beam4","gate50","guard0","guard15"):
                        joint_planner = JointBatchCarbonPlanner(
                            risk_buffer_minutes=frozen_margin,
                            beam_width=4, chunk_size=8
                        )
                    if heldout_batch_planner == "gate50":
                        state_gate = FeasibleCoverageGate(
                            threshold=0.5,min_batch_size=2
                        )
                    if heldout_batch_planner in ("guard0","guard15"):
                        risk_guard=ProjectedRiskGuard(
                            heldout_batch_planner,risk_buffer_minutes=frozen_margin
                        )
                    if heldout_queue_order != "fifo":
                        install_queue_discipline(
                            env.cluster_manager.datacenters,
                            heldout_queue_order
                        )

                policy = test_policy if phase in ("heldout", "heldout_drain") else training_policy
                in_transit = {dc_id: [] for dc_id in by_id}
                for eta, task, dc_name in env.in_transit_tasks:
                    dc_id = env.cluster_manager.datacenters[dc_name].dc_id
                    in_transit[dc_id].append((eta, task))
                policy.set_visible_commitments(in_transit)
                tasks = list(env.current_tasks)
                if phase in ("calibration_drain", "heldout_drain") and tasks:
                    raise AssertionError("Unexpected newly admitted tasks during drain")
                joint_routes = {}
                joint_predicted = {}
                use_joint = phase == "heldout" and joint_planner is not None and bool(tasks)
                if use_joint and state_gate is not None:
                    gate_decision = state_gate.assess(
                        tasks,env.cluster_manager.datacenters,
                        now,env.cluster_manager,in_transit,
                        step_seconds=int(dt.total_seconds())
                    )
                    metrics["test_gate_batches"]+=1
                    metrics["test_gate_tasks"]+=gate_decision["tasks"]
                    metrics["test_gate_feasible_tasks"]+=gate_decision["feasible_tasks"]
                    if gate_decision["activate"]:
                        metrics["test_gate_activated_batches"]+=1
                    use_joint = gate_decision["activate"]
                if use_joint:
                    batch_result = joint_planner.plan(
                        tasks, env.cluster_manager.datacenters,
                        now, env.cluster_manager, in_transit,
                        step_seconds=int(dt.total_seconds())
                    )
                    if risk_guard is not None:
                        review=risk_guard.review(
                            tasks,env.cluster_manager.datacenters,
                            now,env.cluster_manager,in_transit,
                            batch_result,step_seconds=int(dt.total_seconds())
                        )
                        metrics["test_guard_reviewed_batches"]+=1
                        metrics["test_guard_accepted_batches"]+=int(review["accepted"])
                        if review["accepted"]:
                            metrics["test_guard_projected_carbon_delta_accepted"]+=(
                                review["projected_carbon_proxy_delta"]
                            )
                        else:
                            reason=review["reason"]
                            metric={
                                "forecast_sla_regression":"test_guard_rejected_risk",
                                "no_strict_projected_gain":"test_guard_rejected_no_gain",
                                "empty_or_forced_origin":"test_guard_rejected_forced"
                            }[reason]
                            metrics[metric]+=1
                            # Entire batch returns to the actual sequential
                            # greedy dispatcher, not a partially accepted plan.
                            use_joint=False
                    if use_joint:
                        joint_routes = dict(zip(tasks,batch_result["routes"]))
                        joint_predicted = dict(zip(tasks,batch_result["predictions"]))
                    if use_joint:
                        if len(joint_routes) != len(tasks):
                            raise AssertionError("Joint planner duplicated batch tasks")
                        metrics["test_joint_batch_plans"] += 1
                        metrics["test_joint_beam_expansions"] += batch_result["expansions"]
                        metrics["test_joint_chunks"] += batch_result["chunks"]
                actions = []
                for task in tasks:
                    if phase == "heldout" and task in joint_routes:
                        dc_id = joint_routes[task]
                        fallback = False
                    else:
                        dc_id, fallback = policy.choose(
                            task, env.cluster_manager.datacenters,
                            now, env.cluster_manager,
                            step_seconds=int(dt.total_seconds()),
                        )
                    if dc_id == 0:
                        raise AssertionError("This paired holdout disallows temporal deferral")
                    if dc_id not in index_action:
                        raise AssertionError("Unknown selected data center")
                    # Upstream will force late tasks to their origin
                    # without routing delay; use the effective assignment.
                    forced = now > task.sla_deadline
                    effective_id = task.origin_dc_id if forced else dc_id
                    dc = by_id[effective_id]
                    if forced:
                        eta = now
                        prediction = None
                    else:
                        origin = env.cluster_manager.get_dc_location(task.origin_dc_id)
                        delay = float(get_transmission_delay(
                            origin, dc.location,
                            env.cluster_manager.cloud_provider, task.bandwidth_gb
                        ))
                        if not math.isfinite(delay) or delay < 0:
                            raise ValueError("Invalid network delay")
                        ticks = max(1, math.ceil(delay / dt.total_seconds()))
                        prediction = predict_finish(
                            task, dc, now, ticks,
                            step_seconds=int(dt.total_seconds()),
                            known_arrivals=in_transit[effective_id],
                            queue_order=(heldout_forecast_order
                                         if phase == "heldout" else "fifo"),
                        )
                        eta = max(now + dt, now + timedelta(seconds=delay))
                    if phase == "heldout" and task in joint_routes:
                        if prediction != joint_predicted[task]:
                            raise AssertionError(
                                "Batch planner forecast disagrees with actual "
                                "committed route/order"
                            )
                    if phase == "heldout" and audit_candidates:
                        # Must run before the selected task joins in_transit;
                        # all alternative centers see the SAME prior batch
                        # commitments and no future admissions/outcomes.
                        heldout_candidate_snapshots[task] = evaluate_candidates(
                            task, env.cluster_manager.datacenters,
                            now, env.cluster_manager, in_transit,
                            effective_id, step_seconds=int(dt.total_seconds()),
                            buffer_minutes=frozen_margin,
                            forced_origin=forced,
                            queue_order=heldout_forecast_order
                        )
                    if phase == "heldout" and audit_states:
                        heldout_state_snapshots[task] = snapshot_decision(
                            task, dc, now, prediction,
                            in_transit[effective_id],
                            margin_minutes=frozen_margin
                        )
                    in_transit[effective_id].append((eta, task))
                    actions.append(index_action[dc_id])
                    if phase == "calibration":
                        warmup_tasks.add(task)
                        warmup_predictions[task] = prediction
                        warmup_routes.append((task.job_name, effective_id))
                    elif phase == "heldout":
                        heldout_tasks.add(task)
                        heldout_predictions[task] = prediction
                        heldout_decision_buffers[task] = frozen_margin
                        heldout_routes.append((task.job_name, effective_id))
                    else:
                        raise AssertionError("Dispatched a task outside admission windows")

                _, _, terminated, truncated, info = env.step(actions)
                for dc_info in info["datacenter_infos"].values():
                    common = dc_info["__common__"]
                    completed = common["tasks_finished_this_step_objects"]
                    for task in completed:
                        if task in warmup_tasks:
                            if task in warmup_finished:
                                raise AssertionError("Duplicate training completion")
                            warmup_finished.add(task)
                            if step < calibration_steps + gap_steps:
                                calibrator.observe_completed(
                                    task, warmup_predictions[task],
                                    task.finish_time, env.current_time,
                                )
                        elif task in heldout_tasks:
                            if task in heldout_finished:
                                raise AssertionError("Duplicate test completion")
                            heldout_finished.add(task)
                        else:
                            raise AssertionError("Unknown task completion")
                    if phase in ("heldout", "heldout_drain"):
                        metrics["test_sla_met"] += int(common["__sla__"]["met"])
                        metrics["test_sla_violated"] += int(common["__sla__"]["violated"])
                        metrics["test_facility_carbon_kg"] += float(common["carbon_emissions_kg"])
                        metrics["test_facility_cost_usd"] += float(common["energy_cost_USD"])
                if phase in ("heldout", "heldout_drain"):
                    metrics["test_network_carbon_kg"] += float(info["total_emissions_kg"])
                    metrics["test_network_cost_usd"] += float(info["transmission_cost_total_usd"])
                if terminated or truncated:
                    raise AssertionError("Chronological simulator stopped before end of experiment")

            if test_policy is None:
                raise AssertionError("No holdout policy activated")
            metrics["test_tasks_admitted"] = len(heldout_tasks)
            metrics["test_tasks_finished"] = len(heldout_finished)
            metrics["test_finished_work_signature"] = finished_work_signature(
                heldout_finished
            )
            metrics["test_completed_core_minutes"] = sum(
                float(t.cores_req) * float(t.duration)
                for t in heldout_finished
            )
            metrics["test_completed_gpu_minutes"] = sum(
                float(t.gpu_req) * float(t.duration)
                for t in heldout_finished
            )
            metrics["test_unfinished"] = len(heldout_tasks - heldout_finished)
            metrics["test_unfinished_overdue"] = sum(
                task.sla_deadline < env.current_time
                for task in heldout_tasks - heldout_finished
            )
            metrics["test_total_carbon_kg"] = (
                metrics["test_facility_carbon_kg"] + metrics["test_network_carbon_kg"]
            )
            metrics["test_total_cost_usd"] = (
                metrics["test_facility_cost_usd"] + metrics["test_network_cost_usd"]
            )
            if metrics["test_sla_met"] + metrics["test_sla_violated"] != len(heldout_finished):
                raise AssertionError("SLA counts do not conserve completed jobs")
            if not heldout_tasks:
                raise AssertionError("Holdout window had zero workload arrivals")
            # SLA performance denominator is ALL admitted test jobs, including
            # unfinished, not only completed tasks. The incomplete-but-not-
            # overdue cohort is always reported separately.
            metrics["test_completion_rate_admitted"] = (
                len(heldout_finished) / len(heldout_tasks)
            )
            metrics["test_on_time_rate_admitted"] = (
                metrics["test_sla_met"] / len(heldout_tasks)
            )
            metrics["test_deadline_failures_including_overdue"] = (
                metrics["test_sla_violated"] + metrics["test_unfinished_overdue"]
            )
            metrics["test_deadline_failure_rate_admitted"] = (
                metrics["test_deadline_failures_including_overdue"]
                / len(heldout_tasks)
            )
            metrics["test_carbon_per_finished_job_kg"] = (
                metrics["test_total_carbon_kg"] / len(heldout_finished)
                if heldout_finished else None
            )
            all_remaining = (
                [task for dc in by_id.values() for task in dc.pending_tasks]
                + [task for dc in by_id.values() for task in dc.running_tasks]
                + [task for _, task, _ in env.in_transit_tasks]
                + list(env.current_tasks)
            )
            if set(all_remaining) != heldout_tasks - heldout_finished:
                raise AssertionError("Held-out task lifecycle not conserved")

            if audit_candidates:
                if set(heldout_candidate_snapshots) != heldout_tasks:
                    raise AssertionError("Candidate audit missing heldout dispatch")
                feasibility, per_task_candidates = summarize_candidate_audit(
                    heldout_candidate_snapshots, heldout_finished
                )
                if feasibility["completed"] != len(heldout_finished):
                    raise AssertionError("Candidate audit completion mismatch")
                if feasibility["censored_unfinished"] != len(heldout_tasks-heldout_finished):
                    raise AssertionError("Candidate audit censoring mismatch")
                metrics["test_action_feasibility"] = feasibility
                if candidate_audit_dir is not None:
                    directory = Path(candidate_audit_dir)
                    directory.mkdir(parents=True, exist_ok=True)
                    identity = (
                        f"{treatment}_seed{seed}_scale{capacity_scale}_"
                        f"gap{gap_steps}_test{test_steps}"
                    )
                    (directory / (identity + ".jsonl")).write_text(
                        "".join(json.dumps(row, allow_nan=False) + "\n"
                                for row in per_task_candidates),
                        encoding="utf-8"
                    )
            if audit_states:
                if set(heldout_state_snapshots) != heldout_tasks:
                    raise AssertionError("State audit missing a heldout admission")
                pressure_report, pressure_rows = audit_state_risk(
                    heldout_state_snapshots, heldout_finished
                )
                metrics["test_state_risk_total"] = pressure_report["total"]
                metrics["test_state_risk_by_pressure"] = pressure_report["by_predeclared_pressure"]
                if state_audit_dir is not None:
                    directory = Path(state_audit_dir)
                    directory.mkdir(parents=True, exist_ok=True)
                    identity = (
                        f"{treatment}_seed{seed}_scale{capacity_scale}_"
                        f"gap{gap_steps}_test{test_steps}"
                    )
                    (directory / (identity + ".jsonl")).write_text(
                        "".join(json.dumps(row, allow_nan=False) + "\n"
                                for row in pressure_rows),
                        encoding="utf-8"
                    )
            score, _ = summarize_forecasts(
                heldout_predictions, heldout_finished, buffer_minutes=30,
                decision_buffers=heldout_decision_buffers,
            )
            metrics.update({f"test_{key}": value for key, value in score.items()})
            safe_completed = score["decision_margin_predicted_safe_completed"]
            metrics["test_buffered_safe_completed_fraction_of_admitted"] = (
                safe_completed / len(heldout_tasks)
            )
            metrics["test_buffered_safe_completed_fraction_of_completed"] = (
                safe_completed / len(heldout_finished) if heldout_finished else None
            )
            metrics["test_safe_flag_is_vacuous"] = safe_completed == 0
            metrics["test_routing_signature"] = _signature(heldout_routes)
            metrics["test_admission_signature"] = _signature(
                sorted(task.job_name for task in heldout_tasks)
            )
            metrics["train_admission_signature"] = _signature(
                sorted(task.job_name for task in warmup_tasks)
            )
            metrics["pretest_training_sample_is_disjoint"] = (
                not bool(warmup_tasks.intersection(heldout_tasks))
            )
            for key, val in metrics.items():
                if isinstance(val, float) and not math.isfinite(val):
                    raise AssertionError(f"Non-finite {key}")
            return metrics, heldout_routes
        finally:
            close = getattr(env, "close", None)
            if callable(close):
                close()


def compare(seed, **kwargs):
    fixed, fixed_routes = run_one(seed, "fixed_30", **kwargs)
    calibrated, calibrated_routes = run_one(seed, "precalibrated_frozen", **kwargs)
    for field in (
        "train_window_start", "train_admissions_end", "test_window_start",
        "test_admissions_end", "pretest_train_completed",
        "pretest_train_forecast_residuals", "pretest_learned_buffer_minutes",
        "train_routing_signature", "train_admission_signature",
        "test_admission_signature", "test_tasks_admitted",
    ):
        if fixed[field] != calibrated[field]:
            raise AssertionError(f"Paired experimental condition changed: {field}")
    if fixed["applied_frozen_buffer_minutes"] != 30:
        raise AssertionError("Fixed buffer not actually applied")
    if calibrated["applied_frozen_buffer_minutes"] <= 30:
        raise AssertionError("Frozen calibrator did not learn a larger risk buffer")
    if len(fixed_routes) != len(calibrated_routes):
        raise AssertionError("Paired task admission counts mismatch")
    if any(a[0] != b[0] for a, b in zip(fixed_routes, calibrated_routes)):
        raise AssertionError("Paired test arrival order mismatch")
    changes = sum(a[1] != b[1] for a, b in zip(fixed_routes, calibrated_routes))
    for result in (fixed, calibrated):
        result["paired_dispatch_difference_count"] = changes
    return fixed, calibrated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 42])
    parser.add_argument("--calibration-steps", type=int, default=16)
    parser.add_argument("--gap-steps", type=int, default=128)
    parser.add_argument("--test-steps", type=int, default=16)
    parser.add_argument("--drain-steps", type=int, default=96)
    parser.add_argument("--capacity-scale", type=float, default=.02)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "research_sci/results/chronological.json")
    args = parser.parse_args()
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("Use distinct seeds")
    results = []
    for seed in args.seeds:
        fixed, calibrated = compare(
            seed, calibration_steps=args.calibration_steps,
            gap_steps=args.gap_steps, test_steps=args.test_steps,
            drain_steps=args.drain_steps, capacity_scale=args.capacity_scale,
        )
        results.extend((fixed, calibrated))
        for row in (fixed, calibrated):
            print(json.dumps({
                key: row[key] for key in (
                    "seed", "treatment", "pretest_train_completed",
                    "pretest_train_forecast_residuals",
                    "pretest_learned_buffer_minutes", "applied_frozen_buffer_minutes",
                    "test_tasks_admitted", "test_tasks_finished",
                    "test_sla_violated", "test_unfinished_overdue",
                    "test_total_carbon_kg",
                    "test_decision_margin_coverage_completed",
                    "test_decision_margin_false_safe_rate_completed",
                    "paired_dispatch_difference_count",
                )
            }, allow_nan=False), flush=True)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(results, indent=2, allow_nan=False), encoding="utf-8")
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"Chronological held-out results: {args.output}, {csv_path}", flush=True)
    print("NOTE: empirical pretest quantile is NOT a statistically guaranteed SLA risk bound.")


if __name__ == "__main__":
    main()
