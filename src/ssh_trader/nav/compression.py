from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from .features import volatility_features_from_close
from .indicators import atr


@dataclass(frozen=True, slots=True)
class CompressionConfig:
    atr_window: int = 14
    contraction_lookback: int = 50
    vol_pct_window: int = 252
    vol_pct_low_threshold: float = 0.4
    weight_atr: float = 0.4
    weight_range: float = 0.4
    weight_vol: float = 0.2

    range_window: int = 50
    breakout_confirm: int = 1
    vol_expand_threshold: float = 0.7
    score_trigger: float = 0.6

    def __post_init__(self) -> None:
        for name, iv in (
            ("atr_window", self.atr_window),
            ("contraction_lookback", self.contraction_lookback),
            ("vol_pct_window", self.vol_pct_window),
            ("range_window", self.range_window),
            ("breakout_confirm", self.breakout_confirm),
        ):
            if iv <= 0:
                raise ValueError(f"{name} must be positive")
        for name, fv in (
            ("vol_pct_low_threshold", self.vol_pct_low_threshold),
            ("vol_expand_threshold", self.vol_expand_threshold),
            ("score_trigger", self.score_trigger),
        ):
            if not (0.0 < fv <= 1.0) or not math.isfinite(fv):
                raise ValueError(f"{name} must be finite and in (0, 1]")
        for name, w in (
            ("weight_atr", self.weight_atr),
            ("weight_range", self.weight_range),
            ("weight_vol", self.weight_vol),
        ):
            if w < 0.0 or not math.isfinite(w):
                raise ValueError(f"{name} must be finite and non-negative")


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


def compression_score(
    *,
    high: list[float],
    low: list[float],
    close: list[float],
    config: CompressionConfig | None = None,
) -> tuple[list[float | None], list[float | None]]:
    """Compute compression score and rolling compression range width.

    Score is a weighted average of:
    - ATR contraction vs its trailing mean
    - range (high-low) contraction vs its trailing mean
    - volatility percentile below a threshold
    """
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high/low/close must have equal length")
    if not close:
        return [], []

    if config is None:
        config = CompressionConfig()

    atr_series = atr(high, low, close, window=config.atr_window, smoothing="wilder")
    atr_mean = _rolling_mean(atr_series, window=config.contraction_lookback)

    rng = [hi - lo for hi, lo in zip(high, low, strict=True)]
    rng_opt: list[float | None] = [float(x) for x in rng]
    rng_mean = _rolling_mean(rng_opt, window=config.contraction_lookback)

    vol_feats = volatility_features_from_close(
        close=close,
        rv_window=config.atr_window,
        vol_percentile_window=config.vol_pct_window,
        annualization_factor=1.0,
        demean=False,
    )
    vol_pct = vol_feats.vol_percentile

    w_sum = config.weight_atr + config.weight_range + config.weight_vol
    w_atr = config.weight_atr / w_sum if w_sum > 0 else 0.0
    w_rng = config.weight_range / w_sum if w_sum > 0 else 0.0
    w_vol = config.weight_vol / w_sum if w_sum > 0 else 0.0

    score: list[float | None] = [None] * len(close)
    for i in range(len(close)):
        comp = 0.0
        weight = 0.0

        atr_i = atr_series[i]
        atr_m = atr_mean[i]
        if atr_i is not None and atr_m is not None and atr_m > 0:
            ratio = atr_i / atr_m
            atr_comp = max(0.0, min(1.0, 1.0 - ratio))
            comp += w_atr * atr_comp
            weight += w_atr

        rng_m = rng_mean[i]
        if rng_m is not None and rng_m > 0:
            ratio = rng[i] / rng_m
            rng_comp = max(0.0, min(1.0, 1.0 - ratio))
            comp += w_rng * rng_comp
            weight += w_rng

        vol_p = vol_pct[i]
        if vol_p is not None:
            vol_comp = max(
                0.0,
                min(1.0, (config.vol_pct_low_threshold - vol_p) / config.vol_pct_low_threshold),
            )
            comp += w_vol * vol_comp
            weight += w_vol

        if weight > 0.0:
            score[i] = comp / weight

    hi_roll = _rolling_max(high, window=config.range_window)
    lo_roll = _rolling_min(low, window=config.range_window)
    width: list[float | None] = [None] * len(close)
    for i in range(len(close)):
        hi_i = hi_roll[i]
        lo_i = lo_roll[i]
        if hi_i is None or lo_i is None:
            continue
        width[i] = hi_i - lo_i

    return score, width


def expansion_trigger(
    *,
    close: list[float],
    high: list[float],
    low: list[float],
    vol_pct: list[float | None],
    trend: list[int],
    score: list[float | None],
    config: CompressionConfig | None = None,
) -> list[bool]:
    """Detect bullish expansion following compression."""
    if not (len(close) == len(high) == len(low) == len(vol_pct) == len(trend) == len(score)):
        raise ValueError("all series must have equal length")
    if not close:
        return []

    if config is None:
        config = CompressionConfig()

    hi_roll = _rolling_max(high, window=config.range_window)
    trigger: list[bool] = [False] * len(close)
    compressed_confirm = 0
    was_compressed = False
    for i in range(len(close)):
        s = score[i]
        if s is not None and s >= config.score_trigger:
            compressed_confirm += 1
        else:
            compressed_confirm = 0
        if compressed_confirm >= config.breakout_confirm:
            was_compressed = True

        if i == 0:
            continue
        prev_hi = hi_roll[i - 1]
        v = vol_pct[i]
        if prev_hi is None or v is None:
            continue
        if (
            was_compressed
            and close[i] > prev_hi
            and v >= config.vol_expand_threshold
            and trend[i] > 0
        ):
            trigger[i] = True
    return trigger
