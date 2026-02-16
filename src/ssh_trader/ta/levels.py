from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import exp
from typing import Literal

from ssh_trader.nav.indicators import atr as atr_indicator

LevelKind = Literal["support", "resistance"]


@dataclass(frozen=True)
class PivotConfig:
    k: int = 3


@dataclass(frozen=True)
class LevelClusterConfig:
    band_atr_mult: float = 0.3
    min_separation_bars: int = 5
    min_touches: int = 3
    reaction_lookahead: int = 10
    reaction_atr_mult: float = 1.0


@dataclass(frozen=True)
class LevelScoreConfig:
    touch_weight: float = 0.4
    recency_weight: float = 0.3
    reaction_weight: float = 0.3
    recency_half_life: int = 200
    top_n: int = 5


@dataclass(frozen=True)
class Level:
    center: float
    band_low: float
    band_high: float
    touch_count: int
    touch_indices: list[int]
    reaction_strength_atr: float
    score: float
    kind: LevelKind


@dataclass(frozen=True)
class LevelProximity:
    level_index: int | None
    level_kind: LevelKind | None
    distance_price: float | None
    distance_atr: float | None


@dataclass
class _Cluster:
    kind: LevelKind
    touches: list[int]
    prices: list[float]
    atrs: list[float]
    last_idx: int
    center: float


def detect_pivots(
    high: Sequence[float],
    low: Sequence[float],
    config: PivotConfig | None = None,
) -> tuple[list[bool], list[bool]]:
    cfg = config or PivotConfig()
    k = cfg.k
    if k < 1:
        raise ValueError("k must be >= 1")
    n = len(high)
    if len(low) != n:
        raise ValueError("high/low length mismatch")
    piv_high = [False] * n
    piv_low = [False] * n
    for i in range(k, n - k):
        h = high[i]
        lo = low[i]
        if h >= max(high[i - k : i + k + 1]):
            piv_high[i] = True
        if lo <= min(low[i - k : i + k + 1]):
            piv_low[i] = True
    return piv_high, piv_low


def _iter_pivots(
    prices: Sequence[float],
    flags: Sequence[bool],
) -> Iterable[tuple[int, float]]:
    for i, is_pivot in enumerate(flags):
        if is_pivot:
            yield i, prices[i]


def build_levels(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    atr_series: Sequence[float | None] | None = None,
    pivot_config: PivotConfig | None = None,
    cluster_config: LevelClusterConfig | None = None,
    score_config: LevelScoreConfig | None = None,
) -> list[Level]:
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high/low/close must have the same length")
    if atr_series is None:
        atr_series = atr_indicator(high, low, close, window=14, smoothing="wilder")
    if len(atr_series) != len(close):
        raise ValueError("atr series length mismatch")

    piv_high, piv_low = detect_pivots(high, low, pivot_config)
    cfg = cluster_config or LevelClusterConfig()
    score_cfg = score_config or LevelScoreConfig()

    clusters: list[_Cluster] = []

    def add_pivot(idx: int, price: float, kind: LevelKind) -> None:
        atr_i = atr_series[idx]
        if atr_i is None or atr_i <= 0:
            return
        band = cfg.band_atr_mult * float(atr_i)
        for c in clusters:
            if c.kind != kind:
                continue
            center = c.center
            last_idx = c.last_idx
            if abs(price - center) <= band and (idx - last_idx) >= cfg.min_separation_bars:
                c.touches.append(idx)
                c.prices.append(price)
                c.atrs.append(float(atr_i))
                c.last_idx = idx
                c.center = sum(c.prices) / len(c.prices)
                return
        clusters.append(
            _Cluster(
                kind=kind,
                touches=[idx],
                prices=[price],
                atrs=[float(atr_i)],
                last_idx=idx,
                center=price,
            )
        )

    for i, p in _iter_pivots(high, piv_high):
        add_pivot(i, p, "resistance")
    for i, p in _iter_pivots(low, piv_low):
        add_pivot(i, p, "support")

    levels: list[Level] = []
    n = len(close)
    for c in clusters:
        touches = list(c.touches)
        if len(touches) < cfg.min_touches:
            continue
        center = c.center
        atrs = list(c.atrs)
        band = cfg.band_atr_mult * (sum(atrs) / len(atrs))
        reaction_vals: list[float] = []
        for idx, atr_i in zip(touches, atrs, strict=True):
            end = min(n - 1, idx + cfg.reaction_lookahead)
            if c.kind == "support":
                move = max(close[j] - center for j in range(idx, end + 1))
            else:
                move = max(center - close[j] for j in range(idx, end + 1))
            reaction_vals.append(move / atr_i if atr_i > 0 else 0.0)
        reaction = sum(reaction_vals) / len(reaction_vals) if reaction_vals else 0.0
        if reaction < cfg.reaction_atr_mult:
            continue
        levels.append(
            Level(
                center=center,
                band_low=center - band,
                band_high=center + band,
                touch_count=len(touches),
                touch_indices=touches,
                reaction_strength_atr=reaction,
                score=0.0,
                kind=c.kind,
            )
        )

    levels = _score_levels(levels, score_cfg, len(close) - 1)
    return _top_n(levels, score_cfg.top_n)


def _score_levels(levels: list[Level], cfg: LevelScoreConfig, last_idx: int) -> list[Level]:
    if not levels:
        return []
    touch_vals = [lvl.touch_count for lvl in levels]
    react_vals = [lvl.reaction_strength_atr for lvl in levels]
    recency_vals: list[float] = []
    for lvl in levels:
        r = 0.0
        for idx in lvl.touch_indices:
            age = max(0, last_idx - idx)
            r += exp(-age / max(1, cfg.recency_half_life))
        recency_vals.append(r)
    t_min, t_max = min(touch_vals), max(touch_vals)
    r_min, r_max = min(react_vals), max(react_vals)
    c_min, c_max = min(recency_vals), max(recency_vals)

    def norm(val: float, lo: float, hi: float) -> float:
        if hi == lo:
            return 1.0
        return (val - lo) / (hi - lo)

    out: list[Level] = []
    for lvl, tv, rv, cv in zip(levels, touch_vals, react_vals, recency_vals, strict=True):
        score = (
            cfg.touch_weight * norm(float(tv), float(t_min), float(t_max))
            + cfg.recency_weight * norm(float(cv), float(c_min), float(c_max))
            + cfg.reaction_weight * norm(float(rv), float(r_min), float(r_max))
        )
        out.append(
            Level(
                center=lvl.center,
                band_low=lvl.band_low,
                band_high=lvl.band_high,
                touch_count=lvl.touch_count,
                touch_indices=lvl.touch_indices,
                reaction_strength_atr=lvl.reaction_strength_atr,
                score=score,
                kind=lvl.kind,
            )
        )
    return out


def _top_n(levels: list[Level], n: int) -> list[Level]:
    supports = sorted(
        (lvl for lvl in levels if lvl.kind == "support"),
        key=lambda x: x.score,
        reverse=True,
    )
    resist = sorted(
        (lvl for lvl in levels if lvl.kind == "resistance"),
        key=lambda x: x.score,
        reverse=True,
    )
    return supports[:n] + resist[:n]


def compute_level_proximity(
    close: Sequence[float],
    atr_series: Sequence[float | None],
    levels: Sequence[Level],
) -> list[LevelProximity]:
    out: list[LevelProximity] = []
    if not levels:
        return [LevelProximity(None, None, None, None) for _ in close]
    for i, px in enumerate(close):
        nearest_idx: int | None = None
        nearest_dist: float | None = None
        for li, lvl in enumerate(levels):
            dist = abs(px - lvl.center)
            if nearest_dist is None or dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = li
        if nearest_idx is None or nearest_dist is None:
            out.append(LevelProximity(None, None, None, None))
            continue
        atr_i = atr_series[i]
        dist_atr = None if atr_i is None or atr_i <= 0 else nearest_dist / atr_i
        lvl = levels[nearest_idx]
        out.append(LevelProximity(nearest_idx, lvl.kind, nearest_dist, dist_atr))
    return out
