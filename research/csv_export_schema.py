"""Dependency-free CSV column schema for mixed baseline output rows."""


def union_csv_fieldnames(rows):
    """Stable union of every field, preserving first-seen column ordering.

    Baselines without forecast metrics and queue-aware policies with forecast
    metrics must both remain exportable, independent of policy run order.
    """
    fields = list(dict.fromkeys(key for row in rows for key in row))
    if not fields:
        raise ValueError("no result rows for CSV export")
    return fields


