from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .model import OHLCVFrame, to_utc_aware


@dataclass(frozen=True, slots=True)
class CleanStats:
    deduped: int
    sorted: bool
    filled: int


def normalize_and_sort(frame: OHLCVFrame) -> tuple[OHLCVFrame, CleanStats]:
    """Normalize timestamps to UTC, sort ascending, de-duplicate by keeping last."""
    n = len(frame)
    if n == 0:
        return frame, CleanStats(deduped=0, sorted=True, filled=0)

    entries = list(range(n))
    ts_utc = [to_utc_aware(t) for t in frame.ts]

    was_sorted = all(ts_utc[i] <= ts_utc[i + 1] for i in range(n - 1))
    entries.sort(key=lambda i: ts_utc[i])

    # De-duplicate timestamps: keep the last occurrence.
    deduped = 0
    keep: list[int] = []
    last_ts: datetime | None = None
    for idx in entries:
        t = ts_utc[idx]
        if last_ts is not None and t == last_ts:
            deduped += 1
            keep[-1] = idx
        else:
            keep.append(idx)
            last_ts = t

    def take(series: list[float] | None) -> list[float] | None:
        if series is None:
            return None
        return [series[i] for i in keep]

    out = OHLCVFrame(
        ts=[ts_utc[i].astimezone(timezone.utc) for i in keep],
        open=[frame.open[i] for i in keep],
        high=[frame.high[i] for i in keep],
        low=[frame.low[i] for i in keep],
        close=[frame.close[i] for i in keep],
        volume=[frame.volume[i] for i in keep],
        funding=take(frame.funding),
        open_interest=take(frame.open_interest),
    )

    return out, CleanStats(deduped=deduped, sorted=was_sorted, filled=0)


def fill_missing_intervals(
    frame: OHLCVFrame, timeframe_seconds: int
) -> tuple[OHLCVFrame, CleanStats]:
    """Fill missing bars with deterministic synthetic bars.

    Synthetic bars:
    - ts increments by timeframe
    - open/high/low/close = previous close
    - volume = 0
    - funding / open_interest = 0 when present
    """
    if timeframe_seconds <= 0:
        raise ValueError("timeframe_seconds must be positive")
    if len(frame) == 0:
        return frame, CleanStats(deduped=0, sorted=True, filled=0)

    dt = timedelta(seconds=timeframe_seconds)
    ts: list[datetime] = [frame.ts[0]]
    o: list[float] = [frame.open[0]]
    h: list[float] = [frame.high[0]]
    low: list[float] = [frame.low[0]]
    c: list[float] = [frame.close[0]]
    v: list[float] = [frame.volume[0]]

    funding: list[float] | None = [frame.funding[0]] if frame.funding is not None else None
    oi: list[float] | None = [frame.open_interest[0]] if frame.open_interest is not None else None

    filled = 0
    for i in range(1, len(frame)):
        prev_t = ts[-1]
        expected = prev_t + dt
        current = frame.ts[i]
        while expected < current:
            prev_close = c[-1]
            ts.append(expected)
            o.append(prev_close)
            h.append(prev_close)
            low.append(prev_close)
            c.append(prev_close)
            v.append(0.0)
            if funding is not None:
                funding.append(0.0)
            if oi is not None:
                oi.append(0.0)
            filled += 1
            expected = expected + dt

        ts.append(current)
        o.append(frame.open[i])
        h.append(frame.high[i])
        low.append(frame.low[i])
        c.append(frame.close[i])
        v.append(frame.volume[i])
        if funding is not None and frame.funding is not None:
            funding.append(frame.funding[i])
        if oi is not None and frame.open_interest is not None:
            oi.append(frame.open_interest[i])

    out = OHLCVFrame(
        ts=ts,
        open=o,
        high=h,
        low=low,
        close=c,
        volume=v,
        funding=funding,
        open_interest=oi,
    )
    return out, CleanStats(deduped=0, sorted=True, filled=filled)
