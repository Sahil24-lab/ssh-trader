from __future__ import annotations

import math
from datetime import datetime, timezone

from .model import OHLCVFrame


def resample_ohlcv(frame: OHLCVFrame, out_timeframe_seconds: int) -> OHLCVFrame:
    """Resample to a higher timeframe via time-bucketing in UTC epoch seconds.

    Funding is aggregated as mean, open interest as last.
    """
    if out_timeframe_seconds <= 0:
        raise ValueError("out_timeframe_seconds must be positive")
    if len(frame) == 0:
        return frame

    def bucket_start(ts: datetime) -> int:
        epoch = int(ts.replace(tzinfo=timezone.utc).timestamp())
        return (epoch // out_timeframe_seconds) * out_timeframe_seconds

    out_ts: list[datetime] = []
    out_o: list[float] = []
    out_h: list[float] = []
    out_l: list[float] = []
    out_c: list[float] = []
    out_v: list[float] = []
    out_funding: list[float] | None = [] if frame.funding is not None else None
    out_oi: list[float] | None = [] if frame.open_interest is not None else None

    cur_bucket: int | None = None
    b_open = 0.0
    b_high = -math.inf
    b_low = math.inf
    b_close = 0.0
    b_vol = 0.0
    f_sum = 0.0
    f_n = 0
    b_oi = 0.0

    def flush(bucket: int) -> None:
        nonlocal b_open, b_high, b_low, b_close, b_vol, f_sum, f_n, b_oi
        out_ts.append(datetime.fromtimestamp(bucket, tz=timezone.utc))
        out_o.append(b_open)
        out_h.append(b_high)
        out_l.append(b_low)
        out_c.append(b_close)
        out_v.append(b_vol)
        if out_funding is not None:
            out_funding.append((f_sum / f_n) if f_n > 0 else 0.0)
        if out_oi is not None:
            out_oi.append(b_oi)

    for i in range(len(frame)):
        b = bucket_start(frame.ts[i])
        if cur_bucket is None:
            cur_bucket = b
            b_open = frame.open[i]
            b_high = frame.high[i]
            b_low = frame.low[i]
            b_close = frame.close[i]
            b_vol = frame.volume[i]
            if frame.funding is not None:
                f_sum = frame.funding[i]
                f_n = 1
            if frame.open_interest is not None:
                b_oi = frame.open_interest[i]
            continue

        if b != cur_bucket:
            flush(cur_bucket)
            cur_bucket = b
            b_open = frame.open[i]
            b_high = frame.high[i]
            b_low = frame.low[i]
            b_close = frame.close[i]
            b_vol = frame.volume[i]
            if frame.funding is not None:
                f_sum = frame.funding[i]
                f_n = 1
            else:
                f_sum = 0.0
                f_n = 0
            if frame.open_interest is not None:
                b_oi = frame.open_interest[i]
            else:
                b_oi = 0.0
            continue

        b_high = max(b_high, frame.high[i])
        b_low = min(b_low, frame.low[i])
        b_close = frame.close[i]
        b_vol += frame.volume[i]
        if frame.funding is not None:
            f_sum += frame.funding[i]
            f_n += 1
        if frame.open_interest is not None:
            b_oi = frame.open_interest[i]

    if cur_bucket is not None:
        flush(cur_bucket)

    return OHLCVFrame(
        ts=out_ts,
        open=out_o,
        high=out_h,
        low=out_l,
        close=out_c,
        volume=out_v,
        funding=out_funding,
        open_interest=out_oi,
    )
