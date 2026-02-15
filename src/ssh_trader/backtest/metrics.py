from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from ssh_trader.nav.regime import Regime

from .simulator import SimulationResult


@dataclass(frozen=True, slots=True)
class Metrics:
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown: float
    win_rate: float
    exposure_utilization: float
    funding_contribution: float
    directional_contribution: float
    regime_returns: dict[Regime, float]


def _periods_per_year(ts: list[datetime]) -> float:
    if len(ts) < 3:
        return 0.0
    deltas = [(b - a).total_seconds() for a, b in zip(ts[:-1], ts[1:], strict=True)]
    deltas_sorted = sorted(deltas)
    dt = deltas_sorted[len(deltas_sorted) // 2]
    if dt <= 0:
        return 0.0
    return (365.25 * 24.0 * 3600.0) / dt


def _max_drawdown(nav: list[float]) -> float:
    peak = -math.inf
    max_dd = 0.0
    for x in nav:
        if x > peak:
            peak = x
        if peak > 0:
            dd = 1.0 - (x / peak)
            if dd > max_dd:
                max_dd = dd
    return max_dd


def compute_metrics(result: SimulationResult) -> Metrics:
    bars = result.bars
    if not bars:
        return Metrics(
            cagr=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            exposure_utilization=0.0,
            funding_contribution=0.0,
            directional_contribution=0.0,
            regime_returns={},
        )

    ts = [b.ts for b in bars]
    nav = [b.nav for b in bars]

    rets: list[float] = []
    wins = 0
    for i in range(1, len(nav)):
        r = (nav[i] / nav[i - 1]) - 1.0
        rets.append(r)
        if r > 0:
            wins += 1

    win_rate = (wins / len(rets)) if rets else 0.0

    years = (ts[-1] - ts[0]).total_seconds() / (365.25 * 24.0 * 3600.0)
    if years > 0:
        cagr = (nav[-1] / nav[0]) ** (1.0 / years) - 1.0
    else:
        cagr = 0.0

    ppy = _periods_per_year(ts)
    if rets and ppy > 0:
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r) ** 2 for r in rets) / len(rets)
        std = math.sqrt(max(0.0, var))
        sharpe = (mean_r / std) * math.sqrt(ppy) if std > 0 else 0.0

        neg = [r for r in rets if r < 0]
        if neg:
            mean_n = sum(neg) / len(neg)
            var_n = sum((r - mean_n) ** 2 for r in neg) / len(neg)
            down = math.sqrt(max(0.0, var_n))
            sortino = (mean_r / down) * math.sqrt(ppy) if down > 0 else 0.0
        else:
            sortino = 0.0
    else:
        sharpe = 0.0
        sortino = 0.0

    max_dd = _max_drawdown(nav)

    exposure_util = sum(b.gross_exposure / b.nav for b in bars if b.nav > 0) / len(bars)

    funding = sum(b.pnl_funding for b in bars)
    directional = sum(b.pnl_directional_price + b.pnl_directional_funding for b in bars)
    total_pnl = nav[-1] - nav[0]
    funding_contrib = (funding / total_pnl) if total_pnl != 0 else 0.0
    directional_contrib = (directional / total_pnl) if total_pnl != 0 else 0.0

    regime_returns: dict[Regime, float] = {}
    by_regime: dict[Regime, list[float]] = {
        Regime.RISK_OFF: [],
        Regime.NEUTRAL: [],
        Regime.RISK_ON: [],
    }
    for i in range(1, len(bars)):
        by_regime[bars[i].regime].append((bars[i].nav / bars[i - 1].nav) - 1.0)
    for k, xs in by_regime.items():
        regime_returns[k] = (sum(xs) / len(xs)) if xs else 0.0

    return Metrics(
        cagr=cagr,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_dd,
        win_rate=win_rate,
        exposure_utilization=exposure_util,
        funding_contribution=funding_contrib,
        directional_contribution=directional_contrib,
        regime_returns=regime_returns,
    )
