"""Rule-based market regime classifier.

States:
- RISK_OFF: defensive posture
- NEUTRAL: balanced posture
- RISK_ON: directional overlay allowed

Inputs (per bar):
- trend filter: derived from close vs EMA(close)
- volatility percentile: derived from rolling realized volatility
- optional funding sign: +/- signal used as a small modifier
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .features import trend_signal, volatility_features_from_close


class Regime(str, Enum):
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"
    RISK_ON = "RISK_ON"

    def __str__(self) -> str:  # pragma: no cover
        return self.value


@dataclass(frozen=True, slots=True)
class RegimeConfig:
    long_ma_window: int = 200
    trend_method: Literal["sma", "ema"] = "sma"
    trend_span: int = 200
    trend_band: float = 0.0
    rv_window: int = 20
    vol_percentile_window: int = 252
    annualization_factor: float = 1.0
    risk_on_vol_pct_max: float = 0.7
    risk_off_vol_pct_min: float = 0.9
    risk_on_exit_vol_pct: float = 0.8
    risk_off_exit_vol_pct: float = 0.8
    confirm_bars: int = 3
    funding_mode: Literal["ignore", "sign"] = "sign"

    def __post_init__(self) -> None:
        if self.trend_method not in ("sma", "ema"):
            raise ValueError("trend_method must be 'sma' or 'ema'")
        if self.long_ma_window <= 0:
            raise ValueError("long_ma_window must be positive")
        if self.trend_span <= 0:
            raise ValueError("trend_span must be positive")
        if self.rv_window <= 0:
            raise ValueError("rv_window must be positive")
        if self.vol_percentile_window <= 0:
            raise ValueError("vol_percentile_window must be positive")
        if self.confirm_bars <= 0:
            raise ValueError("confirm_bars must be positive")
        if self.annualization_factor <= 0.0 or not math.isfinite(self.annualization_factor):
            raise ValueError("annualization_factor must be finite and positive")
        if self.trend_band < 0.0 or not math.isfinite(self.trend_band):
            raise ValueError("trend_band must be finite and non-negative")
        for name, value in (
            ("risk_on_vol_pct_max", self.risk_on_vol_pct_max),
            ("risk_off_vol_pct_min", self.risk_off_vol_pct_min),
            ("risk_on_exit_vol_pct", self.risk_on_exit_vol_pct),
            ("risk_off_exit_vol_pct", self.risk_off_exit_vol_pct),
        ):
            if not (0.0 < value <= 1.0) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite and in (0, 1]")
        if self.funding_mode not in ("ignore", "sign"):
            raise ValueError("funding_mode must be 'ignore' or 'sign'")


def _funding_sign_series(funding: list[float] | None) -> list[int] | None:
    if funding is None:
        return None
    out: list[int] = []
    for f in funding:
        if not math.isfinite(f):
            raise ValueError("funding must be finite")
        if f > 0.0:
            out.append(1)
        elif f < 0.0:
            out.append(-1)
        else:
            out.append(0)
    return out


def next_regime(
    *,
    previous: Regime,
    trend: int,
    vol_pct: float,
    config: RegimeConfig,
    funding_sign: int | None = None,
) -> Regime:
    """State transition with simple hysteresis."""
    if trend not in (-1, 0, 1):
        raise ValueError("trend must be in {-1, 0, 1}")
    if not (0.0 < vol_pct <= 1.0) or not math.isfinite(vol_pct):
        raise ValueError("vol_pct must be finite and in (0, 1]")
    if funding_sign is not None and funding_sign not in (-1, 0, 1):
        raise ValueError("funding_sign must be in {-1, 0, 1}")

    # Immediate risk-off trigger on extreme volatility.
    if vol_pct >= config.risk_off_vol_pct_min:
        return Regime.RISK_OFF

    # Tentative classification without considering previous state.
    tentative: Regime
    if trend > 0 and vol_pct <= config.risk_on_vol_pct_max:
        tentative = Regime.RISK_ON
    else:
        tentative = Regime.NEUTRAL

    # Funding modifier (optional).
    if config.funding_mode == "sign" and funding_sign is not None:
        if tentative == Regime.RISK_ON and funding_sign > 0:
            tentative = Regime.NEUTRAL
        elif (
            tentative == Regime.NEUTRAL
            and funding_sign < 0
            and trend > 0
            and vol_pct <= config.risk_on_vol_pct_max
        ):
            tentative = Regime.RISK_ON

    # Hysteresis: make it easier to *stay* in a regime than to *enter*.
    if previous == Regime.RISK_ON:
        if trend >= 0 and vol_pct <= config.risk_on_exit_vol_pct:
            return Regime.RISK_ON
        return Regime.NEUTRAL

    if previous == Regime.RISK_OFF:
        if vol_pct >= config.risk_off_exit_vol_pct:
            return Regime.RISK_OFF
        return Regime.NEUTRAL

    return tentative


def classify_regimes(
    *,
    close: list[float],
    high: list[float] | None = None,
    low: list[float] | None = None,
    funding: list[float] | None = None,
    config: RegimeConfig | None = None,
    initial: Regime = Regime.NEUTRAL,
) -> list[Regime]:
    """Compute a regime label for each close.

    Notes:
    - Realized volatility is computed from log returns of close.
    - Volatility percentile uses a trailing window on the realized volatility series.
    - ``high``/``low`` are accepted for future extensions but not required by this classifier.
    """
    if high is not None and len(high) != len(close):
        raise ValueError("high must match close length")
    if low is not None and len(low) != len(close):
        raise ValueError("low must match close length")
    if funding is not None and len(funding) != len(close):
        raise ValueError("funding must match close length")

    if not close:
        return []

    if config is None:
        config = RegimeConfig()

    trend = trend_signal(
        close=close,
        method=config.trend_method,
        window_or_span=(
            config.long_ma_window if config.trend_method == "sma" else config.trend_span
        ),
        band=config.trend_band,
    )
    vol_feats = volatility_features_from_close(
        close=close,
        rv_window=config.rv_window,
        vol_percentile_window=config.vol_percentile_window,
        annualization_factor=config.annualization_factor,
        demean=False,
    )
    vol_pct_full = vol_feats.vol_percentile

    funding_sign = _funding_sign_series(funding) if config.funding_mode != "ignore" else None

    regimes: list[Regime] = []
    prev = initial
    pending: Regime | None = None
    pending_count = 0
    for i in range(len(close)):
        v = vol_pct_full[i]
        if v is None or trend[i] == 0:
            regimes.append(prev)
            pending = None
            pending_count = 0
            continue

        desired = next_regime(
            previous=prev,
            trend=trend[i],
            vol_pct=v,
            config=config,
            funding_sign=(funding_sign[i] if funding_sign is not None else None),
        )

        if desired == prev:
            regimes.append(prev)
            pending = None
            pending_count = 0
            continue

        # Risk-off is conservative: allow immediate transition on trigger.
        if desired == Regime.RISK_OFF:
            prev = desired
            regimes.append(prev)
            pending = None
            pending_count = 0
            continue

        if pending == desired:
            pending_count += 1
        else:
            pending = desired
            pending_count = 1

        if pending_count >= config.confirm_bars:
            prev = desired
            pending = None
            pending_count = 0

        regimes.append(prev)

    return regimes
