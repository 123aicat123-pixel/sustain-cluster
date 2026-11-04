"""Causal rolling upper-residual margin for completion-time forecasts.

Only an OBSERVED completion may add a residual (finish - prediction).
Dispatch-time decisions use residuals from earlier completed jobs only.
This adaptive empirical quantile is NOT distribution-free coverage: policy
feedback, nonexchangeability and censored unfinished jobs break guarantees.
"""
from collections import deque
import math


class OnlineResidualCalibrator:
    def __init__(self, alpha=0.1, min_samples=20, window=256,
                 fallback_minutes=30.0):
        if not 0 < alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        if min_samples < 2 or window < min_samples:
            raise ValueError("Invalid sample window")
        if not math.isfinite(fallback_minutes) or fallback_minutes < 0:
            raise ValueError("Invalid fallback")
        self.alpha = float(alpha)
        self.min_samples = int(min_samples)
        self.residuals = deque(maxlen=window)
        self.fallback_minutes = float(fallback_minutes)
        self.seen = set()
        self.last_time = None
        self.observed_count = 0
        self.no_forecast_count = 0
        self.margin_at_last_update = self.fallback_minutes

    def margin_minutes(self):
        """Conservative nonnegative empirical upper quantile of recent errors."""
        n = len(self.residuals)
        if n < self.min_samples:
            return self.fallback_minutes
        ordered = sorted(self.residuals)
        rank = math.ceil((n + 1) * (1 - self.alpha))
        # If the formal rank falls beyond observed n, a finite upper bound
        # is not supported. Continue using the largest observed residual as
        # a heuristic; deliberately DO NOT claim conformal coverage.
        rank = min(n, max(1, rank))
        return max(self.fallback_minutes, 0.0, ordered[rank - 1])

    def observe_completed(self, task, prediction, actual_finish, observed_at):
        """Update only after simulator confirms completion, never before."""
        if task in self.seen:
            raise AssertionError("Completion recorded more than once")
        if self.last_time is not None and observed_at < self.last_time:
            raise ValueError("Completion observations must be chronological")
        if actual_finish > observed_at:
            raise AssertionError("Cannot learn from a future completion")
        self.seen.add(task)
        self.last_time = observed_at
        if prediction is None:
            self.no_forecast_count += 1
            return
        error = (actual_finish - prediction).total_seconds() / 60
        if not math.isfinite(error):
            raise ValueError("Non-finite residual")
        self.residuals.append(error)
        self.observed_count += 1
        self.margin_at_last_update = self.margin_minutes()

    def summary(self):
        return {
            "calibration_alpha_target": self.alpha,
            "calibration_completed_observations": self.observed_count,
            "calibration_completed_no_forecast": self.no_forecast_count,
            "calibration_window_sample_count": len(self.residuals),
            "calibration_min_samples": self.min_samples,
            "calibration_buffer_last_minutes": self.margin_minutes(),
            "calibration_is_coverage_guarantee": False,
        }
