from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from ssh_trader.data.model import OHLCVFrame
from ssh_trader.guidance.policy import GuidancePolicy, TargetAllocations
from ssh_trader.nav.compression import CompressionConfig, compression_score, expansion_trigger
from ssh_trader.nav.features import trend_signal, volatility_features_from_close
from ssh_trader.nav.regime import Regime, RegimeConfig, classify_regimes
from ssh_trader.risk.governor import RiskDecision, RiskGovernor


@dataclass(frozen=True, slots=True)
class FeeModel:
    taker_fee_bps: float = 5.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.taker_fee_bps) or self.taker_fee_bps < 0.0:
            raise ValueError("taker_fee_bps must be finite and non-negative")

    def fee(self, notional: float) -> float:
        return abs(notional) * (self.taker_fee_bps / 1e4)


@dataclass(frozen=True, slots=True)
class SlippageModel:
    """Quadratic slippage cost model based on trade size vs NAV."""

    slippage_bps_at_1x_nav: float = 10.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.slippage_bps_at_1x_nav) or self.slippage_bps_at_1x_nav < 0.0:
            raise ValueError("slippage_bps_at_1x_nav must be finite and non-negative")

    def cost(self, *, trade_notional: float, nav: float) -> float:
        if nav <= 0.0 or not math.isfinite(nav):
            raise ValueError("nav must be finite and positive")
        x = abs(trade_notional) / nav
        return abs(trade_notional) * (self.slippage_bps_at_1x_nav / 1e4) * x


@dataclass(frozen=True, slots=True)
class SimulatorConfig:
    initial_nav: float = 1_000_000.0
    carry_funding_freq_hours: int = 8
    liquidation_buffer: float = 0.10
    target_dir_vol: float = 0.20
    min_dir_vol: float = 1e-6

    def __post_init__(self) -> None:
        if not math.isfinite(self.initial_nav) or self.initial_nav <= 0.0:
            raise ValueError("initial_nav must be finite and positive")
        if self.carry_funding_freq_hours <= 0:
            raise ValueError("carry_funding_freq_hours must be positive")
        if not math.isfinite(self.liquidation_buffer) or not (0.0 <= self.liquidation_buffer < 1.0):
            raise ValueError("liquidation_buffer must be finite and in [0, 1)")
        if not math.isfinite(self.target_dir_vol) or self.target_dir_vol <= 0.0:
            raise ValueError("target_dir_vol must be finite and positive")
        if not math.isfinite(self.min_dir_vol) or self.min_dir_vol <= 0.0:
            raise ValueError("min_dir_vol must be finite and positive")


@dataclass(slots=True)
class PortfolioState:
    cash: float
    carry_spot_qty: float
    carry_perp_qty: float
    dir_perp_qty: float
    peak_nav: float
    mode: Literal["normal", "carry_only", "flat"]


@dataclass(frozen=True, slots=True)
class TradeEvent:
    ts: datetime
    leg: Literal["spot", "perp"]
    qty_delta: float
    price: float
    notional: float
    fee: float
    slippage: float


@dataclass(frozen=True, slots=True)
class BarResult:
    ts: datetime
    nav: float
    regime: Regime
    carry_notional: float
    directional_notional: float
    gross_exposure: float
    leverage: float
    pnl_price: float
    pnl_directional_price: float
    pnl_carry_price: float
    pnl_funding: float
    pnl_directional_funding: float
    pnl_carry_funding: float
    pnl_fees: float
    pnl_slippage: float
    kill_switch_active: bool


@dataclass(frozen=True, slots=True)
class SimulationResult:
    bars: list[BarResult]
    trades: list[TradeEvent]


def _nav(state: PortfolioState, price: float) -> float:
    # Perp is marked-to-market: its PnL is embedded via qty * price.
    return (
        state.cash
        + state.carry_spot_qty * price
        + (state.carry_perp_qty + state.dir_perp_qty) * price
    )


def _gross_exposure(state: PortfolioState, price: float) -> float:
    spot_notional = abs(state.carry_spot_qty * price)
    perp_notional = abs((state.carry_perp_qty + state.dir_perp_qty) * price)
    return spot_notional + perp_notional


def _apply_trade(
    *,
    state: PortfolioState,
    ts: datetime,
    leg: Literal["spot", "perp"],
    qty_delta: float,
    price: float,
    fee_model: FeeModel,
    slippage_model: SlippageModel,
    trades: list[TradeEvent],
) -> tuple[float, float]:
    if qty_delta == 0.0:
        return 0.0, 0.0

    notional = qty_delta * price
    fee = fee_model.fee(notional)
    nav = _nav(state, price)
    slip = slippage_model.cost(trade_notional=notional, nav=nav)

    if leg == "spot":
        state.carry_spot_qty += qty_delta
        state.cash -= notional
    else:
        # Perp deltas are applied by the caller to the appropriate component.
        pass
        state.cash -= 0.0

    state.cash -= fee + slip
    trades.append(
        TradeEvent(
            ts=ts,
            leg=leg,
            qty_delta=qty_delta,
            price=price,
            notional=notional,
            fee=fee,
            slippage=slip,
        )
    )
    return fee, slip


def simulate_portfolio(
    *,
    frame: OHLCVFrame,
    guidance: GuidancePolicy,
    risk: RiskGovernor,
    fee_model: FeeModel | None = None,
    slippage_model: SlippageModel | None = None,
    nav_config: RegimeConfig | None = None,
    compression_config: CompressionConfig | None = None,
    sim_config: SimulatorConfig | None = None,
) -> SimulationResult:
    """Event-driven portfolio simulator (no live execution).

    Implements:
    - carry engine: spot long + perp short (delta-neutral)
    - directional overlay: perp long, only in RISK_ON and expansion trigger
    - risk governor: leverage cap, venue cap, drawdown kill-switch, vol spike de-risk
    - deterministic fee + slippage models
    """
    if len(frame) == 0:
        return SimulationResult(bars=[], trades=[])

    fee_model = fee_model if fee_model is not None else FeeModel()
    slippage_model = slippage_model if slippage_model is not None else SlippageModel()
    sim_config = sim_config if sim_config is not None else SimulatorConfig()

    nav_config = nav_config if nav_config is not None else RegimeConfig()
    compression_config = (
        compression_config if compression_config is not None else CompressionConfig()
    )

    regimes = classify_regimes(
        close=frame.close,
        high=frame.high,
        low=frame.low,
        funding=frame.funding,
        config=nav_config,
        initial=Regime.NEUTRAL,
    )

    vol_feats = volatility_features_from_close(
        close=frame.close,
        rv_window=nav_config.rv_window,
        vol_percentile_window=nav_config.vol_percentile_window,
        annualization_factor=nav_config.annualization_factor,
        demean=False,
    )
    trend = trend_signal(
        close=frame.close,
        method=nav_config.trend_method,
        window_or_span=(
            nav_config.long_ma_window if nav_config.trend_method == "sma" else nav_config.trend_span
        ),
        band=nav_config.trend_band,
    )
    comp_score, _ = compression_score(
        high=frame.high,
        low=frame.low,
        close=frame.close,
        config=compression_config,
    )
    exp = expansion_trigger(
        close=frame.close,
        high=frame.high,
        low=frame.low,
        vol_pct=vol_feats.vol_percentile,
        trend=trend,
        score=comp_score,
        config=compression_config,
    )

    state = PortfolioState(
        cash=sim_config.initial_nav,
        carry_spot_qty=0.0,
        carry_perp_qty=0.0,
        dir_perp_qty=0.0,
        peak_nav=sim_config.initial_nav,
        mode="normal",
    )

    bars: list[BarResult] = []
    trades: list[TradeEvent] = []

    prev_price = frame.close[0]
    funding_accum = 0.0
    for i, ts in enumerate(frame.ts):
        price = frame.close[i]
        if price <= 0.0 or not math.isfinite(price):
            raise ValueError("close prices must be finite and strictly positive")

        pnl_price = 0.0
        pnl_dir_price = 0.0
        pnl_carry_price = 0.0
        pnl_funding = 0.0
        pnl_dir_funding = 0.0
        pnl_carry_funding = 0.0
        pnl_fees = 0.0
        pnl_slip = 0.0

        if i > 0:
            dpx = price - prev_price
            pnl_dir_price = state.dir_perp_qty * dpx
            pnl_carry_price = (state.carry_spot_qty + state.carry_perp_qty) * dpx
            pnl_price = pnl_dir_price + pnl_carry_price

            if frame.funding is not None:
                funding_accum += frame.funding[i]
                if (i % sim_config.carry_funding_freq_hours) == 0:
                    carry_notional = state.carry_perp_qty * price
                    dir_notional = state.dir_perp_qty * price
                    pnl_carry_funding = -funding_accum * carry_notional
                    pnl_dir_funding = -funding_accum * dir_notional
                    pnl_funding = pnl_carry_funding + pnl_dir_funding
                    state.cash += pnl_funding
                    funding_accum = 0.0

        nav_now = _nav(state, price)
        if nav_now > state.peak_nav:
            state.peak_nav = nav_now

        requested_directional = regimes[i] == Regime.RISK_ON and exp[i]
        decision = risk.decide(
            nav=nav_now,
            peak_nav=state.peak_nav,
            vol_pct=vol_feats.vol_percentile[i],
            requested_directional=requested_directional,
        )
        state.mode = decision.mode

        targets = guidance.targets(regimes[i])
        carry_frac, dir_frac = _apply_risk_constraints_to_targets(
            targets=targets,
            decision=decision,
            nav=nav_now,
            vol=vol_feats.realized_vol[i],
            sim_config=sim_config,
            expansion=exp[i],
        )

        carry_notional = carry_frac * nav_now
        dir_notional = dir_frac * nav_now

        carry_spot_qty = carry_notional / price
        carry_perp_qty = -carry_spot_qty
        dir_perp_qty = dir_notional / price

        target_spot_qty = carry_spot_qty
        target_carry_perp_qty = carry_perp_qty
        target_dir_perp_qty = dir_perp_qty
        target_perp_qty = target_carry_perp_qty + target_dir_perp_qty

        # Enforce leverage cap (gross / nav) by scaling positions down if needed.
        gross_target = abs(target_spot_qty * price) + abs(target_perp_qty * price)
        leverage_target = (gross_target / nav_now) if nav_now > 0 else 0.0
        effective_leverage_cap = decision.leverage_cap_applied * (
            1.0 - sim_config.liquidation_buffer
        )
        if leverage_target > effective_leverage_cap:
            s = effective_leverage_cap / leverage_target
            target_spot_qty *= s
            target_perp_qty *= s
            carry_notional *= s
            dir_notional *= s

        # Apply trades at bar close.
        spot_delta = target_spot_qty - state.carry_spot_qty
        carry_perp_delta = target_carry_perp_qty - state.carry_perp_qty
        dir_perp_delta = target_dir_perp_qty - state.dir_perp_qty

        fee, slip = _apply_trade(
            state=state,
            ts=ts,
            leg="spot",
            qty_delta=spot_delta,
            price=price,
            fee_model=fee_model,
            slippage_model=slippage_model,
            trades=trades,
        )
        pnl_fees -= fee
        pnl_slip -= slip

        # Perp deltas: book as separate events for carry vs directional attribution.
        if carry_perp_delta != 0.0:
            notional = carry_perp_delta * price
            fee = fee_model.fee(notional)
            nav_for_slip = _nav(state, price)
            slip = slippage_model.cost(trade_notional=notional, nav=nav_for_slip)
            state.carry_perp_qty += carry_perp_delta
            state.cash -= fee + slip
            trades.append(
                TradeEvent(
                    ts=ts,
                    leg="perp",
                    qty_delta=carry_perp_delta,
                    price=price,
                    notional=notional,
                    fee=fee,
                    slippage=slip,
                )
            )
            pnl_fees -= fee
            pnl_slip -= slip

        if dir_perp_delta != 0.0:
            notional = dir_perp_delta * price
            fee = fee_model.fee(notional)
            nav_for_slip = _nav(state, price)
            slip = slippage_model.cost(trade_notional=notional, nav=nav_for_slip)
            state.dir_perp_qty += dir_perp_delta
            state.cash -= fee + slip
            trades.append(
                TradeEvent(
                    ts=ts,
                    leg="perp",
                    qty_delta=dir_perp_delta,
                    price=price,
                    notional=notional,
                    fee=fee,
                    slippage=slip,
                )
            )
            pnl_fees -= fee
            pnl_slip -= slip

        # Post-trade leverage enforcement: costs can reduce NAV enough to exceed cap.
        _post_trade_enforce_leverage(
            state=state,
            ts=ts,
            price=price,
            leverage_cap=decision.leverage_cap_applied * (1.0 - sim_config.liquidation_buffer),
            fee_model=fee_model,
            slippage_model=slippage_model,
            trades=trades,
        )

        nav_after = _nav(state, price)
        gross = _gross_exposure(state, price)
        leverage = gross / nav_after if nav_after > 0 else 0.0

        bars.append(
            BarResult(
                ts=ts,
                nav=nav_after,
                regime=regimes[i],
                carry_notional=carry_notional,
                directional_notional=dir_notional,
                gross_exposure=gross,
                leverage=leverage,
                pnl_price=pnl_price,
                pnl_directional_price=pnl_dir_price,
                pnl_carry_price=pnl_carry_price,
                pnl_funding=pnl_funding,
                pnl_directional_funding=pnl_dir_funding,
                pnl_carry_funding=pnl_carry_funding,
                pnl_fees=pnl_fees,
                pnl_slippage=pnl_slip,
                kill_switch_active=decision.kill_switch_active,
            )
        )
        prev_price = price

    return SimulationResult(bars=bars, trades=trades)


def _post_trade_enforce_leverage(
    *,
    state: PortfolioState,
    ts: datetime,
    price: float,
    leverage_cap: float,
    fee_model: FeeModel,
    slippage_model: SlippageModel,
    trades: list[TradeEvent],
) -> None:
    for _ in range(3):
        nav = _nav(state, price)
        gross = _gross_exposure(state, price)
        if nav <= 0.0 or gross <= 0.0:
            return
        if gross <= leverage_cap * nav + 1e-12:
            return

        s = (leverage_cap * nav) / gross
        target_carry_spot = state.carry_spot_qty * s
        target_carry_perp = state.carry_perp_qty * s
        target_dir_perp = state.dir_perp_qty * s

        spot_delta = target_carry_spot - state.carry_spot_qty
        if spot_delta != 0.0:
            _apply_trade(
                state=state,
                ts=ts,
                leg="spot",
                qty_delta=spot_delta,
                price=price,
                fee_model=fee_model,
                slippage_model=slippage_model,
                trades=trades,
            )

        carry_perp_delta = target_carry_perp - state.carry_perp_qty
        if carry_perp_delta != 0.0:
            notional = carry_perp_delta * price
            fee = fee_model.fee(notional)
            nav_for_slip = _nav(state, price)
            slip = slippage_model.cost(trade_notional=notional, nav=nav_for_slip)
            state.carry_perp_qty += carry_perp_delta
            state.cash -= fee + slip
            trades.append(
                TradeEvent(
                    ts=ts,
                    leg="perp",
                    qty_delta=carry_perp_delta,
                    price=price,
                    notional=notional,
                    fee=fee,
                    slippage=slip,
                )
            )

        dir_perp_delta = target_dir_perp - state.dir_perp_qty
        if dir_perp_delta != 0.0:
            notional = dir_perp_delta * price
            fee = fee_model.fee(notional)
            nav_for_slip = _nav(state, price)
            slip = slippage_model.cost(trade_notional=notional, nav=nav_for_slip)
            state.dir_perp_qty += dir_perp_delta
            state.cash -= fee + slip
            trades.append(
                TradeEvent(
                    ts=ts,
                    leg="perp",
                    qty_delta=dir_perp_delta,
                    price=price,
                    notional=notional,
                    fee=fee,
                    slippage=slip,
                )
            )


def _apply_risk_constraints_to_targets(
    *,
    targets: TargetAllocations,
    decision: RiskDecision,
    nav: float,
    vol: float | None,
    sim_config: SimulatorConfig,
    expansion: bool,
) -> tuple[float, float]:
    _ = nav
    carry = targets.carry_frac
    directional = targets.directional_frac

    if decision.mode == "flat":
        return 0.0, 0.0
    if decision.mode == "carry_only":
        directional = 0.0

    if not decision.directional_allowed or not expansion:
        directional = 0.0

    if vol is None:
        directional = 0.0
    else:
        v = max(sim_config.min_dir_vol, float(vol))
        scale = min(1.0, sim_config.target_dir_vol / v)
        directional *= scale

    # Enforce venue capital cap by clipping deployed capital.
    deployed = carry + directional
    cap = decision.venue_cap_applied
    if deployed > cap and deployed > 0.0:
        s = cap / deployed
        carry *= s
        directional *= s

    return carry, directional
