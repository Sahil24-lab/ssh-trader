from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class Timeframe(str, Enum):
    """Timeframe identifier used for resampling / gap filling."""

    S1 = "1s"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def seconds(self) -> int:
        return parse_timeframe(self.value).seconds


@dataclass(frozen=True, slots=True)
class ParsedTimeframe:
    seconds: int

    @property
    def delta(self) -> timedelta:
        return timedelta(seconds=self.seconds)


def parse_timeframe(value: str) -> ParsedTimeframe:
    """Parse timeframe strings like ``'1h'``, ``'15m'``, ``'1d'``."""
    s = value.strip().lower()
    if not s:
        raise ValueError("timeframe is empty")

    unit = s[-1]
    n_str = s[:-1]
    if unit not in ("s", "m", "h", "d") or not n_str.isdigit():
        raise ValueError(f"invalid timeframe: {value!r}")

    n = int(n_str)
    if n <= 0:
        raise ValueError("timeframe must be positive")

    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return ParsedTimeframe(seconds=n * mult)


@dataclass(frozen=True, slots=True)
class OHLCVFrame:
    """Timestamp-aligned OHLCV (+ optional series) frame.

    All timestamps must be timezone-aware and normalized to UTC.
    """

    ts: list[datetime]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]
    funding: list[float] | None = None
    open_interest: list[float] | None = None

    def __post_init__(self) -> None:
        n = len(self.ts)
        if not (
            len(self.open)
            == len(self.high)
            == len(self.low)
            == len(self.close)
            == len(self.volume)
            == n
        ):
            raise ValueError("all OHLCV lists must have the same length")
        if self.funding is not None and len(self.funding) != n:
            raise ValueError("funding must match ts length")
        if self.open_interest is not None and len(self.open_interest) != n:
            raise ValueError("open_interest must match ts length")

        for t in self.ts:
            if t.tzinfo is None:
                raise ValueError("timestamps must be timezone-aware")
            if t.utcoffset() != timedelta(0):
                raise ValueError("timestamps must be UTC-normalized")

        for high_value, low_value in zip(self.high, self.low, strict=True):
            if high_value < low_value:
                raise ValueError("high must be >= low")

        for series in (
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            (self.funding if self.funding is not None else []),
            (self.open_interest if self.open_interest is not None else []),
        ):
            for v in series:
                if not math.isfinite(v):
                    raise ValueError("series values must be finite")

    def __len__(self) -> int:
        return len(self.ts)

    def timeframe_seconds_inferred(self) -> int:
        """Infer timeframe seconds via median delta between timestamps."""
        if len(self.ts) < 3:
            raise ValueError("need at least 3 timestamps to infer timeframe")
        deltas = [(b - a).total_seconds() for a, b in zip(self.ts[:-1], self.ts[1:], strict=True)]
        deltas_sorted = sorted(deltas)
        mid = deltas_sorted[len(deltas_sorted) // 2]
        if mid <= 0:
            raise ValueError("non-increasing timestamps")
        return int(mid)

    def copy(self) -> OHLCVFrame:
        return OHLCVFrame(
            ts=list(self.ts),
            open=list(self.open),
            high=list(self.high),
            low=list(self.low),
            close=list(self.close),
            volume=list(self.volume),
            funding=list(self.funding) if self.funding is not None else None,
            open_interest=list(self.open_interest) if self.open_interest is not None else None,
        )


def to_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
