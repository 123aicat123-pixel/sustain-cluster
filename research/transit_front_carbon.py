"""Conservative exploratory Pareto-front carbon selection.

Only optimizer-cached surrogate values and per-candidate predicted missed
deadlines are used; no hindsight, no future arrivals, no real simulator
facility carbon at decision time. This is NOT an SLA safety guarantee.
"""
from __future__ import annotations

import math


def choose_front_carbon_under_risk(selected, candidates, predicted_misses):
    """Return (chosen chromosome, changed) from an already-evaluated front.

    Both predicted missed-deadline COUNT and total predicted tardiness must
    not exceed the standard NSGA-II knee solution. Select the lowest
    incremental surrogate-carbon solution within that constraint, then
    lower tardiness, lower cost, and stable chromosome order to break ties.
    If no STRICT carbon proxy reduction exists, keep original.
    """
    selected = tuple(selected)
    if not candidates:
        raise ValueError("expected nonempty cached Pareto front")
    options = {}
    for item in candidates:
        chrom = tuple(item["chromosome"])
        score = tuple(float(v) for v in item["surrogate"])
        if len(score) != 3 or any(not math.isfinite(v) for v in score):
            raise ValueError("invalid front objective record")
        if chrom not in predicted_misses:
            raise ValueError("front candidate missing predicted miss count")
        missed = int(predicted_misses[chrom])
        if missed < 0:
            raise ValueError("negative predicted miss count")
        if chrom in options and options[chrom] != (score, missed):
            raise ValueError("conflicting front records")
        options[chrom] = (score, missed)
    if selected not in options:
        raise ValueError("knee chromosome missing from front")
    reference_score, ref_misses = options[selected]
    eligible = [
        (chrom, score, missed)
        for chrom, (score, missed) in options.items()
        if missed <= ref_misses
        and score[2] <= reference_score[2] + 1e-9
        and score[1] < reference_score[1] - 1e-12
    ]
    if not eligible:
        return list(selected), False
    chosen, _, _ = min(
        eligible,
        key=lambda x: (x[1][1], x[1][2], x[1][0], x[0]),
    )
    return list(chosen), True


def choose_front_carbon_under_taskwise_finish(
        selected, candidates, predicted_finish_offsets):
    """Post-search carbon choice with per-task non-later finish forecasts.

    Each proposed task completion must be no later than for the selected knee
    chromosome, according to the SAME observed-state queue predictor. Unlike
    aggregate tardiness constraints, this cannot exchange an individual task's
    higher predicted risk for another task's improvement. Still no real-world
    SLA guarantee: all estimates omit future admissions and facility behavior.

    Does not call the fitness function or change the optimizer's search budget.
    """
    selected = tuple(selected)
    if not candidates:
        raise ValueError("empty cached final front")
    options = {}
    for entry in candidates:
        chrom = tuple(entry["chromosome"])
        score = tuple(float(x) for x in entry["surrogate"])
        if len(score) != 3 or not all(math.isfinite(x) for x in score):
            raise ValueError("invalid cached three-objective surrogate")
        if chrom not in predicted_finish_offsets:
            raise ValueError("missing candidate's cached per-task finish forecasts")
        finishes = tuple(float(v) for v in predicted_finish_offsets[chrom])
        if not finishes or any(not math.isfinite(v) for v in finishes):
            raise ValueError("invalid predicted finish times")
        if chrom in options and options[chrom] != (score, finishes):
            raise ValueError("conflicting cached front records")
        options[chrom] = (score, finishes)
    if selected not in options:
        raise ValueError("selected knee missing from final front")
    ref_score, ref_finishes = options[selected]
    eligible = []
    for chrom, (score, finishes) in options.items():
        if len(finishes) != len(ref_finishes):
            raise ValueError("inconsistent task cohort length")
        if score[1] >= ref_score[1] - 1e-12:
            continue
        if all(f <= r + 1e-9 for f, r in zip(finishes, ref_finishes)):
            eligible.append((chrom, score))
    if not eligible:
        return list(selected), False
    best, _ = min(eligible, key=lambda x: (x[1][1], x[1][2], x[1][0], x[0]))
    return list(best), True
