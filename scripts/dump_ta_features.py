#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from collections import deque
from datetime import timezone
from pathlib import Path

from ssh_trader.data.clean import fill_missing_intervals, normalize_and_sort
from ssh_trader.data.io_csv import load_ohlcv_csv
from ssh_trader.data.model import OHLCVFrame, parse_timeframe
from ssh_trader.nav.indicators import atr, ema, sma


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Dump TA feature columns for inspection/tuning.")
    p.add_argument("--csv-1h", type=Path, required=True, help="1H OHLCV CSV path.")
    p.add_argument("--csv-4h", type=Path, default=None, help="Optional 4H OHLCV CSV path.")
    p.add_argument("--output", type=Path, required=True, help="Output CSV path.")
    p.add_argument("--fill-missing", action="store_true", help="Fill missing 1H bars first.")
    p.add_argument(
        "--range-window",
        type=int,
        default=24,
        help="Range window (bars) (default: 24).",
    )
    p.add_argument("--vol-window", type=int, default=50, help="Volume zscore window (default: 50).")
    p.add_argument("--pivot-k", type=int, default=3, help="Pivot half-window k (default: 3).")
    p.add_argument(
        "--breakout-atr-x",
        type=float,
        default=0.10,
        help="Breakout distance threshold in ATR units (default: 0.10).",
    )
    p.add_argument(
        "--sweep-atr-w",
        type=float,
        default=0.20,
        help="Sweep distance threshold in ATR units (default: 0.20).",
    )
    p.add_argument(
        "--wick-body-min",
        type=float,
        default=1.5,
        help="Min wick/body ratio for sweep candles (default: 1.5).",
    )
    return p


def _rolling_mean(values: list[float | None], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    q: deque[float] = deque()
    s = 0.0
    for i, v in enumerate(values):
        if v is None:
            q.clear()
            s = 0.0
            continue
        q.append(v)
        s += v
        if len(q) > window:
            s -= q.popleft()
        if len(q) == window:
            out[i] = s / window
    return out


def _rolling_max(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    q: deque[tuple[int, float]] = deque()
    for i, v in enumerate(values):
        while q and q[-1][1] <= v:
            q.pop()
        q.append((i, v))
        start = i - window + 1
        while q and q[0][0] < start:
            q.popleft()
        if i >= window - 1:
            out[i] = q[0][1]
    return out


def _rolling_min(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    q: deque[tuple[int, float]] = deque()
    for i, v in enumerate(values):
        while q and q[-1][1] >= v:
            q.pop()
        q.append((i, v))
        start = i - window + 1
        while q and q[0][0] < start:
            q.popleft()
        if i >= window - 1:
            out[i] = q[0][1]
    return out


def _true_range(high: list[float], low: list[float], close: list[float]) -> list[float]:
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high/low/close must have equal length")
    if not close:
        return []
    out: list[float] = []
    prev_close = close[0]
    for i, (hi, lo, c) in enumerate(zip(high, low, close, strict=True)):
        if i == 0:
            out.append(hi - lo)
        else:
            out.append(max(hi - lo, abs(hi - prev_close), abs(lo - prev_close)))
        prev_close = c
    return out


def _vol_z(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    q: deque[float] = deque()
    s = 0.0
    s2 = 0.0
    for i, v in enumerate(values):
        q.append(v)
        s += v
        s2 += v * v
        if len(q) > window:
            old = q.popleft()
            s -= old
            s2 -= old * old
        if len(q) == window:
            mean = s / window
            var = max(0.0, (s2 / window) - mean * mean)
            std = math.sqrt(var)
            out[i] = (v - mean) / std if std > 0 else 0.0
    return out


def _clv(high: list[float], low: list[float], close: list[float]) -> list[float | None]:
    out: list[float | None] = [None] * len(close)
    for i in range(len(close)):
        rng = high[i] - low[i]
        if rng <= 0:
            out[i] = None
        else:
            out[i] = (close[i] - low[i]) / rng
    return out


def _pivot_flags(high: list[float], low: list[float], k: int) -> tuple[list[bool], list[bool]]:
    if k <= 0:
        raise ValueError("pivot k must be positive")
    if len(high) != len(low):
        raise ValueError("high/low must have equal length")
    n = len(high)
    piv_hi = [False] * n
    piv_lo = [False] * n
    for i in range(k, n - k):
        hi = high[i]
        lo = low[i]
        is_hi = True
        is_lo = True
        for j in range(i - k, i + k + 1):
            if j == i:
                continue
            if high[j] >= hi:
                is_hi = False
            if low[j] <= lo:
                is_lo = False
            if not is_hi and not is_lo:
                break
        piv_hi[i] = is_hi
        piv_lo[i] = is_lo
    return piv_hi, piv_lo


def _wick_stats(
    open_: list[float], high: list[float], low: list[float], close: list[float]
) -> tuple[list[float], list[float], list[float]]:
    if not (len(open_) == len(high) == len(low) == len(close)):
        raise ValueError("open/high/low/close must have equal length")
    body: list[float] = [0.0] * len(close)
    lower_wick: list[float] = [0.0] * len(close)
    upper_wick: list[float] = [0.0] * len(close)
    for i in range(len(close)):
        body[i] = abs(close[i] - open_[i])
        lower_wick[i] = min(open_[i], close[i]) - low[i]
        upper_wick[i] = high[i] - max(open_[i], close[i])
    return body, lower_wick, upper_wick


def _clip01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _load_frame(csv_path: Path, *, timeframe: str, fill_missing: bool) -> OHLCVFrame:
    frame = load_ohlcv_csv(csv_path)
    frame, _ = normalize_and_sort(frame)
    if fill_missing:
        tf_seconds = parse_timeframe(timeframe).seconds
        frame, _ = fill_missing_intervals(frame, tf_seconds)
    return frame


def _bias_from_4h(frame_4h: OHLCVFrame) -> dict[int, int]:
    ema20 = ema(frame_4h.close, span=20)
    ema50 = ema(frame_4h.close, span=50)
    out: dict[int, int] = {}
    for i, ts in enumerate(frame_4h.ts):
        b = 0
        if ema20[i] > ema50[i] and frame_4h.close[i] > ema20[i]:
            b = 1
        elif ema20[i] < ema50[i] and frame_4h.close[i] < ema20[i]:
            b = -1
        epoch = int(ts.replace(tzinfo=timezone.utc).timestamp())
        bucket = (epoch // (4 * 3600)) * (4 * 3600)
        out[bucket] = b
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    frame = _load_frame(args.csv_1h, timeframe="1h", fill_missing=args.fill_missing)

    bias_map: dict[int, int] = {}
    if args.csv_4h is not None and args.csv_4h.exists():
        frame_4h = _load_frame(args.csv_4h, timeframe="4h", fill_missing=False)
        bias_map = _bias_from_4h(frame_4h)

    atr14 = atr(frame.high, frame.low, frame.close, window=14)
    atr_mean50 = _rolling_mean(atr14, window=50)
    atr_ratio: list[float | None] = [None] * len(frame)
    for i in range(len(frame)):
        a = atr14[i]
        m = atr_mean50[i]
        if a is None or m is None or m == 0:
            atr_ratio[i] = None
        else:
            atr_ratio[i] = a / m

    hi_roll = _rolling_max(frame.high, window=args.range_window)
    lo_roll = _rolling_min(frame.low, window=args.range_window)
    rng: list[float | None] = [None] * len(frame)
    for i in range(len(frame)):
        hi = hi_roll[i]
        lo = lo_roll[i]
        if hi is None or lo is None:
            continue
        rng[i] = hi - lo

    rng_slope: list[float | None] = [None] * len(frame)
    for i in range(len(frame)):
        if rng[i] is None or i < args.range_window or rng[i - args.range_window] is None:
            continue
        prev = float(rng[i - args.range_window])
        cur = float(rng[i])
        rng_slope[i] = (cur - prev) / prev if prev > 0 else None

    tr = _true_range(frame.high, frame.low, frame.close)
    tr_mean50 = sma(tr, window=50)
    tr_ratio: list[float | None] = [None] * len(frame)
    for i in range(len(frame)):
        m = tr_mean50[i]
        if m is None or m == 0:
            tr_ratio[i] = None
        else:
            tr_ratio[i] = tr[i] / m

    vol_z = _vol_z(frame.volume, window=args.vol_window)
    clv = _clv(frame.high, frame.low, frame.close)

    piv_hi, piv_lo = _pivot_flags(frame.high, frame.low, k=args.pivot_k)
    body, lower_wick, upper_wick = _wick_stats(frame.open, frame.high, frame.low, frame.close)

    breakout_long: list[bool] = [False] * len(frame)
    breakout_short: list[bool] = [False] * len(frame)
    sweep_reclaim_long: list[bool] = [False] * len(frame)
    sweep_reclaim_short: list[bool] = [False] * len(frame)

    for i in range(1, len(frame)):
        prev_hi = hi_roll[i - 1]
        prev_lo = lo_roll[i - 1]
        a = atr14[i]
        clv_i = clv[i]
        if prev_hi is not None and prev_lo is not None and a is not None and clv_i is not None:
            x = args.breakout_atr_x * a
            if clv_i >= 0.7 and frame.close[i] > float(prev_hi) + x:
                breakout_long[i] = True
            if clv_i <= 0.3 and frame.close[i] < float(prev_lo) - x:
                breakout_short[i] = True

            w = args.sweep_atr_w * a
            b = body[i]
            if b > 0:
                if (
                    lower_wick[i] / b >= args.wick_body_min
                    and frame.low[i] < float(prev_lo) - w
                    and frame.close[i] > float(prev_lo)
                ):
                    sweep_reclaim_long[i] = True
                if (
                    upper_wick[i] / b >= args.wick_body_min
                    and frame.high[i] > float(prev_hi) + w
                    and frame.close[i] < float(prev_hi)
                ):
                    sweep_reclaim_short[i] = True

    compress_flag: list[bool] = [False] * len(frame)
    for i in range(len(frame)):
        ar = atr_ratio[i]
        rs = rng_slope[i]
        if ar is None or rs is None:
            continue
        compress_flag[i] = (ar < 0.8) and (rs < 0.0)

    confluence_long: list[float | None] = [None] * len(frame)
    confluence_short: list[float | None] = [None] * len(frame)
    for i in range(len(frame)):
        a = atr14[i]
        if a is None or a == 0:
            continue

        f_compress = 0.0
        if atr_ratio[i] is not None:
            f_compress = _clip01((0.8 - float(atr_ratio[i])) / 0.8)

        f_volume = 0.0
        if vol_z[i] is not None:
            f_volume = _clip01(float(vol_z[i]) / 2.0)

        f_bias_long = 0.0
        f_bias_short = 0.0
        if bias_map:
            epoch = int(frame.ts[i].replace(tzinfo=timezone.utc).timestamp())
            bucket4 = (epoch // (4 * 3600)) * (4 * 3600)
            b = bias_map.get(bucket4, 0)
            f_bias_long = 1.0 if b > 0 else 0.0
            f_bias_short = 1.0 if b < 0 else 0.0

        f_trig_long = 0.0
        f_trig_short = 0.0
        if i > 0:
            prev_hi = hi_roll[i - 1]
            prev_lo = lo_roll[i - 1]
            if prev_hi is not None:
                f_trig_long = _clip01((frame.close[i] - float(prev_hi)) / a)
            if prev_lo is not None:
                f_trig_short = _clip01((float(prev_lo) - frame.close[i]) / a)

        confluence_long[i] = (
            0.20 * f_compress + 0.35 * f_trig_long + 0.25 * f_volume + 0.20 * f_bias_long
        )
        confluence_short[i] = (
            0.20 * f_compress + 0.35 * f_trig_short + 0.25 * f_volume + 0.20 * f_bias_short
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "timestamp",
                "close",
                "atr14",
                "atr_ratio",
                "range_w",
                "range_slope",
                "vol_z",
                "clv",
                "tr_ratio",
                "bias_4h",
                "pivot_high",
                "pivot_low",
                "body",
                "lower_wick",
                "upper_wick",
                "compress",
                "breakout_long",
                "breakout_short",
                "sweep_reclaim_long",
                "sweep_reclaim_short",
                "confluence_long",
                "confluence_short",
            ]
        )
        for i, ts in enumerate(frame.ts):
            epoch = int(ts.replace(tzinfo=timezone.utc).timestamp())
            bucket4 = (epoch // (4 * 3600)) * (4 * 3600)
            b = bias_map.get(bucket4) if bias_map else None
            w.writerow(
                [
                    ts.isoformat().replace("+00:00", "Z"),
                    frame.close[i],
                    "" if atr14[i] is None else atr14[i],
                    "" if atr_ratio[i] is None else atr_ratio[i],
                    "" if rng[i] is None else rng[i],
                    "" if rng_slope[i] is None else rng_slope[i],
                    "" if vol_z[i] is None else vol_z[i],
                    "" if clv[i] is None else clv[i],
                    "" if tr_ratio[i] is None else tr_ratio[i],
                    "" if b is None else b,
                    "1" if piv_hi[i] else "0",
                    "1" if piv_lo[i] else "0",
                    body[i],
                    lower_wick[i],
                    upper_wick[i],
                    "1" if compress_flag[i] else "0",
                    "1" if breakout_long[i] else "0",
                    "1" if breakout_short[i] else "0",
                    "1" if sweep_reclaim_long[i] else "0",
                    "1" if sweep_reclaim_short[i] else "0",
                    "" if confluence_long[i] is None else confluence_long[i],
                    "" if confluence_short[i] is None else confluence_short[i],
                ]
            )

    print(f"wrote {len(frame)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
