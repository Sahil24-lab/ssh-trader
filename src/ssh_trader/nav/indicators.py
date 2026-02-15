"""Lightweight, dependency-free indicator utilities.

These functions are intentionally implemented without numpy/pandas to keep the core
library small and easy to type-check under strict mypy settings.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from typing import Literal


def log_returns(prices: Sequence[float]) -> list[float]:
    """Compute log returns ln(p_t / p_{t-1}) for a price series.

    Returns a list of length ``len(prices) - 1``.
    """
    if len(prices) < 2:
        return []

    out: list[float] = []
    prev = prices[0]
    if prev <= 0.0 or not math.isfinite(prev):
        raise ValueError("prices must be finite and strictly positive")

    for price in prices[1:]:
        if price <= 0.0 or not math.isfinite(price):
            raise ValueError("prices must be finite and strictly positive")
        out.append(math.log(price / prev))
        prev = price
    return out


def sma(values: Sequence[float], window: int) -> list[float | None]:
    """Simple moving average over a rolling window.

    For indices with insufficient history, the result is ``None``.
    """
    if window <= 0:
        raise ValueError("window must be positive")

    out: list[float | None] = [None] * len(values)
    running_sum = 0.0
    q: deque[float] = deque()

    for idx, value in enumerate(values):
        if not math.isfinite(value):
            raise ValueError("values must be finite")

        q.append(value)
        running_sum += value

        if len(q) > window:
            running_sum -= q.popleft()

        if len(q) == window:
            out[idx] = running_sum / window

    return out


def ema(values: Sequence[float], span: int) -> list[float]:
    """Exponential moving average using standard ``alpha = 2 / (span + 1)``.

    The first EMA value is seeded with the first observation (no warm-up Nones).
    """
    if span <= 0:
        raise ValueError("span must be positive")
    if not values:
        return []

    alpha = 2.0 / (span + 1.0)
    first = values[0]
    if not math.isfinite(first):
        raise ValueError("values must be finite")

    out: list[float] = [first]
    prev = first
    for value in values[1:]:
        if not math.isfinite(value):
            raise ValueError("values must be finite")
        prev = prev + alpha * (value - prev)
        out.append(prev)
    return out


def _true_ranges(high: Sequence[float], low: Sequence[float], close: Sequence[float]) -> list[float]:
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high/low/close must have the same length")
    if not high:
        return []

    tr: list[float] = []
    prev_close = close[0]
    for idx, (h, l, c) in enumerate(zip(high, low, close, strict=True)):
        if not (math.isfinite(h) and math.isfinite(l) and math.isfinite(c)):
            raise ValueError("high/low/close must be finite")
        if h < l:
            raise ValueError("high must be >= low")

        if idx == 0:
            tr.append(h - l)
        else:
            tr.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
        prev_close = c
    return tr


def atr(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    window: int = 14,
    *,
    smoothing: Literal["wilder", "sma"] = "wilder",
) -> list[float | None]:
    """Average True Range (ATR).

    - ``smoothing="wilder"`` uses Wilder's recursive smoothing.
    - ``smoothing="sma"`` uses a simple moving average of true ranges.
    """
    if window <= 0:
        raise ValueError("window must be positive")

    tr = _true_ranges(high, low, close)
    if not tr:
        return []

    if smoothing == "sma":
        return sma(tr, window)

    out: list[float | None] = [None] * len(tr)
    if len(tr) < window:
        return out

    first_atr = sum(tr[:window]) / window
    out[window - 1] = first_atr
    prev_atr = first_atr

    for idx in range(window, len(tr)):
        prev_atr = (prev_atr * (window - 1) + tr[idx]) / window
        out[idx] = prev_atr

    return out


def realized_volatility(
    returns: Sequence[float],
    window: int,
    *,
    annualization_factor: float = 1.0,
    demean: bool = False,
) -> list[float | None]:
    """Rolling realized volatility over ``window`` returns.

    By default this computes ``sqrt(mean(r^2)) * sqrt(annualization_factor)``.
    Set ``demean=True`` to use ``sqrt(mean((r-mean(r))^2))`` instead.
    """
    if window <= 0:
        raise ValueError("window must be positive")
    if annualization_factor <= 0.0 or not math.isfinite(annualization_factor):
        raise ValueError("annualization_factor must be finite and positive")

    out: list[float | None] = [None] * len(returns)
    q: deque[float] = deque()
    sum_r = 0.0
    sum_r2 = 0.0

    for idx, r in enumerate(returns):
        if not math.isfinite(r):
            raise ValueError("returns must be finite")

        q.append(r)
        sum_r += r
        sum_r2 += r * r

        if len(q) > window:
            old = q.popleft()
            sum_r -= old
            sum_r2 -= old * old

        if len(q) == window:
            if demean:
                mean_r = sum_r / window
                var = max(0.0, (sum_r2 / window) - mean_r * mean_r)
            else:
                var = sum_r2 / window
            out[idx] = math.sqrt(var) * math.sqrt(annualization_factor)

    return out


def volatility_percentile(volatility: Sequence[float], window: int) -> list[float | None]:
    """Rolling percentile rank of volatility within a trailing window.

    The percentile is computed as ``count(window_values <= current) / window`` and
    lies in the interval ``(0, 1]`` once warmed up.
    """
    if window <= 0:
        raise ValueError("window must be positive")

    out: list[float | None] = [None] * len(volatility)
    q: deque[float] = deque()

    for idx, v in enumerate(volatility):
        if not math.isfinite(v):
            raise ValueError("volatility must be finite")
        q.append(v)
        if len(q) > window:
            q.popleft()

        if len(q) == window:
            current = q[-1]
            count_le = sum(1 for x in q if x <= current)
            out[idx] = count_le / window

    return out


def drawdown(values: Sequence[float]) -> list[float]:
    """Compute drawdown series (value / peak - 1)."""
    if not values:
        return []

    out: list[float] = []
    peak = values[0]
    if not math.isfinite(peak):
        raise ValueError("values must be finite")
    out.append(0.0)

    for value in values[1:]:
        if not math.isfinite(value):
            raise ValueError("values must be finite")
        if value > peak:
            peak = value
        out.append((value / peak) - 1.0)

    return out

