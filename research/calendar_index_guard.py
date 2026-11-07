"""Research-runner guard for invalid approximate calendar-day indexes.

The upstream factory approximates site-telemetry day-of-year as
month*30.5 + day. That can exceed the simulator's 0..364 supported
indices near year end. Preserve *all* preexisting in-range indices to
avoid retroactively changing earlier benchmark conditions. For invalid
indices only, use the exact calendar date's zero-based day-of-year.

This is a trace-initialization repair, NOT a scheduling algorithm change.
"""
from datetime import date
import math


def correct_overflowed_init_day(approx_index, *, year, month, day):
    """Return (resolved_index, was_corrected), preserving in-range legacy."""
    if not isinstance(approx_index, int) or isinstance(approx_index, bool):
        raise TypeError("site initialization index must be an integer")
    check = date(int(year), int(month), int(day))
    if 0 <= approx_index <= 364:
        return approx_index, False
    # SustainDC site/weather/carbon traces currently have 365 day indices.
    # An exact day outside that range (e.g. leap-year Dec 31) must not wrap
    # invisibly and fetch data from the wrong part of the year.
    correct = check.timetuple().tm_yday - 1
    if not 0 <= correct <= 364:
        raise ValueError("calendar date not representable on a 365-day trace")
    return correct, True
