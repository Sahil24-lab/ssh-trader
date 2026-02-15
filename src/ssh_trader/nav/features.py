from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .indicators import ema, log_returns, realized_volatility, sma, volatility_percentile


@dataclass(frozen=True, slots=True)
class VolatilityFeatures:
    log_returns: list[float]
    realized_vol: list[float | None]
    vol_percentile: list[float | None]


def trend_signal(
    *,
    close: list[float],
    method: Literal["sma", "ema"],
    window_or_span: int,
    band: float = 0.0,
) -> list[int]:
    if window_or_span <= 0:
        raise ValueError("window_or_span must be positive")
    if band < 0.0 or not math.isfinite(band):
        raise ValueError("band must be finite and non-negative")
    if not close:
        return []

    if method == "ema":
        ma: list[float | None] = [float(x) for x in ema(close, span=window_or_span)]
    else:
        ma = sma(close, window=window_or_span)

    out: list[int] = []
    for c, m in zip(close, ma, strict=True):
        if m is None:
            out.append(0)
        elif c > m * (1.0 + band):
            out.append(1)
        elif c < m * (1.0 - band):
            out.append(-1)
        else:
            out.append(0)
    return out


def volatility_features_from_close(
    *,
    close: list[float],
    rv_window: int,
    vol_percentile_window: int,
    annualization_factor: float = 1.0,
    demean: bool = False,
) -> VolatilityFeatures:
    if not close:
        return VolatilityFeatures(log_returns=[], realized_vol=[], vol_percentile=[])

    rets = log_returns(close)
    rv = realized_volatility(
        rets,
        window=rv_window,
        annualization_factor=annualization_factor,
        demean=demean,
    )

    rv_aligned: list[float | None] = [None]
    rv_aligned.extend(rv)

    rv_vals = [v for v in rv_aligned if v is not None]
    vol_pct_vals = volatility_percentile(rv_vals, window=vol_percentile_window)

    vol_pct: list[float | None] = [None] * len(close)
    start = next((i for i, v in enumerate(rv_aligned) if v is not None), len(close))
    for i in range(start, len(close)):
        if rv_aligned[i] is None:
            continue
        vol_pct[i] = vol_pct_vals[i - start]

    return VolatilityFeatures(log_returns=rets, realized_vol=rv_aligned, vol_percentile=vol_pct)
