from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from .model import to_utc_aware


def count_missing_intervals(ts: Sequence[datetime], timeframe_seconds: int) -> int:
    """Count missing intervals in a timestamp series.

    Intervals are measured as multiples of ``timeframe_seconds`` between adjacent timestamps.
    Returns the total number of missing bars between the first and last timestamp.

    Notes:
    - Timestamps are normalized to UTC for comparisons.
    - This assumes the series is strictly increasing and aligned to the timeframe.
    """
    if timeframe_seconds <= 0:
        raise ValueError("timeframe_seconds must be positive")
    if len(ts) < 2:
        return 0

    ts_utc = [to_utc_aware(t) for t in ts]
    missing = 0
    for a, b in zip(ts_utc[:-1], ts_utc[1:], strict=True):
        delta = (b - a).total_seconds()
        if delta <= 0:
            raise ValueError("timestamps must be strictly increasing")
        steps = int(round(delta / timeframe_seconds))
        if abs(delta - (steps * timeframe_seconds)) > 1.0:
            raise ValueError("timestamps are not aligned to timeframe_seconds")
        if steps > 1:
            missing += steps - 1
    return missing
