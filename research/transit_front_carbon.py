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
