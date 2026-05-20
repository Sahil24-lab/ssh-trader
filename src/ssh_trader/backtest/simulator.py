from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    order_latency_bars: int = 1
    fill_range_position: float = 0.75
    fill_time_fraction: float = 0.25
    directional_stop_loss_pct: float = 0.02
    directional_take_profit_pct: float = 0.04
    directional_max_hold_bars: int = 24
    carry_rebalance_threshold_pct: float = 0.01

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
        if self.order_latency_bars < 0:
            raise ValueError("order_latency_bars must be non-negative")
        if not math.isfinite(self.fill_range_position) or not (
            0.0 <= self.fill_range_position <= 1.0
        ):
            raise ValueError("fill_range_position must be finite and in [0, 1]")
        if not math.isfinite(self.fill_time_fraction) or not (
            0.0 <= self.fill_time_fraction < 1.0
        ):
            raise ValueError("fill_time_fraction must be finite and in [0, 1)")
        if not math.isfinite(self.directional_stop_loss_pct) or self.directional_stop_loss_pct <= 0.0:
            raise ValueError("directional_stop_loss_pct must be finite and positive")
        if (
            not math.isfinite(self.directional_take_profit_pct)
            or self.directional_take_profit_pct <= 0.0
        ):
            raise ValueError("directional_take_profit_pct must be finite and positive")
        if self.directional_max_hold_bars <= 0:
            raise ValueError("directional_max_hold_bars must be positive")
        if not math.isfinite(self.carry_rebalance_threshold_pct) or self.carry_rebalance_threshold_pct < 0.0:
            raise ValueError("carry_rebalance_threshold_pct must be finite and non-negative")


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
    source: Literal["carry", "directional"]
    qty_delta: float
    price: float
    notional: float
    fee: float
    slippage: float


@dataclass(frozen=True, slots=True)
class TradeLifecycle:
    open_ts: datetime
    close_ts: datetime
    kind: Literal["directional", "carry"]
    side: Literal["long", "short", "carry"]
    qty: float
    entry_price: float
    exit_price: float
    nav_entry: float
    nav_exit: float
    nav_delta: float
    nav_delta_pct: float | None
    pnl_price: float
    pnl_funding: float
    pnl_fees: float
    pnl_slippage: float
    pnl_total: float
    bars_held: int
    exit_reason: str


@dataclass(frozen=True, slots=True)
class BarResult:
    ts: datetime
    price: float
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
    lifecycles: list[TradeLifecycle]


@dataclass(frozen=True, slots=True)
class PendingTarget:
    signal_idx: int
    spot_qty: float
    carry_perp_qty: float
    dir_perp_qty: float


def _nav(state: PortfolioState, price: float) -> float:
    # Spot is a paid asset (cash outlay). Perps are marked-to-market via cash PnL updates.
    return state.cash + state.carry_spot_qty * price


def _gross_exposure(state: PortfolioState, price: float) -> float:
    spot_notional = abs(state.carry_spot_qty * price)
    perp_notional = abs((state.carry_perp_qty + state.dir_perp_qty) * price)
    return spot_notional + perp_notional


def _apply_trade(
    *,
    state: PortfolioState,
    ts: datetime,
    leg: Literal["spot", "perp"],
    source: Literal["carry", "directional"],
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
            source=source,
            qty_delta=qty_delta,
            price=price,
            notional=notional,
            fee=fee,
            slippage=slip,
        )
    )
    return fee, slip


def _execution_price(
    *,
    frame: OHLCVFrame,
    idx: int,
    qty_delta: float,
    config: SimulatorConfig,
) -> float:
    high = frame.high[idx]
    low = frame.low[idx]
    close = frame.close[idx]
    if high <= 0.0 or low <= 0.0 or high < low:
        raise ValueError("high/low prices must be finite, positive, and high >= low")
    if qty_delta == 0.0:
        return close

    span = high - low
    if qty_delta > 0.0:
        return low + span * config.fill_range_position
    return high - span * config.fill_range_position


def _execution_ts(
    *,
    frame: OHLCVFrame,
    idx: int,
    timeframe_seconds: int,
    config: SimulatorConfig,
) -> datetime:
    return frame.ts[idx] + timedelta(seconds=timeframe_seconds * config.fill_time_fraction)


def _apply_perp_trade(
    *,
    state: PortfolioState,
    ts: datetime,
    source: Literal["carry", "directional"],
    qty_delta: float,
    fill_price: float,
    mark_price: float,
    fee_model: FeeModel,
    slippage_model: SlippageModel,
    trades: list[TradeEvent],
) -> tuple[float, float, float]:
    if qty_delta == 0.0:
        return 0.0, 0.0, 0.0

    notional = qty_delta * fill_price
    fee = fee_model.fee(notional)
    nav_for_slip = _nav(state, mark_price)
    slip = slippage_model.cost(trade_notional=notional, nav=nav_for_slip)
    if source == "carry":
        state.carry_perp_qty += qty_delta
    else:
        state.dir_perp_qty += qty_delta
    mark_pnl = qty_delta * (mark_price - fill_price)
    state.cash += mark_pnl
    state.cash -= fee + slip
    trades.append(
        TradeEvent(
            ts=ts,
            leg="perp",
            source=source,
            qty_delta=qty_delta,
            price=fill_price,
            notional=notional,
            fee=fee,
            slippage=slip,
        )
    )
    return fee, slip, mark_pnl


def _clip_target_qty(pending_qty: float, current_allowed_qty: float) -> float:
    if current_allowed_qty == 0.0:
        return 0.0
    if pending_qty == 0.0:
        return 0.0
    if pending_qty > 0.0 and current_allowed_qty < 0.0:
        return 0.0
    if pending_qty < 0.0 and current_allowed_qty > 0.0:
        return 0.0
    size = min(abs(pending_qty), abs(current_allowed_qty))
    return math.copysign(size, pending_qty)


def _within_rebalance_threshold(current_qty: float, target_qty: float, threshold_pct: float) -> bool:
    if target_qty == 0.0:
        return abs(current_qty) == 0.0
    if current_qty == 0.0:
        return False
    return abs(target_qty - current_qty) / abs(target_qty) < threshold_pct


def _directional_exit(
    *,
    side_qty: float,
    entry_price: float,
    bars_held: int,
    high: float,
    low: float,
    regime: Regime,
    decision: RiskDecision,
    config: SimulatorConfig,
) -> tuple[float | None, str | None]:
    if side_qty == 0.0:
        return None, None

    if decision.mode != "normal":
        return None, "risk_block"
    if regime != Regime.RISK_ON:
        return None, "regime_invalid"
    if bars_held >= config.directional_max_hold_bars:
        return None, "max_hold"

    if side_qty > 0.0:
        stop = entry_price * (1.0 - config.directional_stop_loss_pct)
        take = entry_price * (1.0 + config.directional_take_profit_pct)
        if low <= stop:
            return stop, "stop_loss"
        if high >= take:
            return take, "take_profit"
        return None, None

    stop = entry_price * (1.0 + config.directional_stop_loss_pct)
    take = entry_price * (1.0 - config.directional_take_profit_pct)
    if high >= stop:
        return stop, "stop_loss"
    if low <= take:
        return take, "take_profit"
    return None, None


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
        return SimulationResult(bars=[], trades=[], lifecycles=[])

    fee_model = fee_model if fee_model is not None else FeeModel()
    slippage_model = slippage_model if slippage_model is not None else SlippageModel()
    sim_config = sim_config if sim_config is not None else SimulatorConfig()
    timeframe_seconds = frame.timeframe_seconds_inferred() if len(frame) >= 3 else 0

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
    lifecycles: list[TradeLifecycle] = []

    prev_price = frame.close[0]
    funding_accum = 0.0
    dir_open = False
    dir_entry_ts = frame.ts[0]
    dir_entry_idx = 0
    dir_entry_price = 0.0
    dir_entry_qty = 0.0
    dir_entry_nav = sim_config.initial_nav
    dir_fee_accum = 0.0
    dir_slip_accum = 0.0
    dir_funding_accum = 0.0
    carry_open = False
    carry_entry_ts = frame.ts[0]
    carry_entry_idx = 0
    carry_entry_price = 0.0
    carry_entry_qty = 0.0
    carry_entry_nav = sim_config.initial_nav
    carry_fee_accum = 0.0
    carry_slip_accum = 0.0
    carry_price_accum = 0.0
    carry_funding_accum = 0.0
    prev_regime = regimes[0]
    pending_targets: list[PendingTarget] = []
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
            pnl_carry_price = (state.carry_spot_qty * dpx) + (state.carry_perp_qty * dpx)
            pnl_price = pnl_dir_price + pnl_carry_price
            # Perp PnL is realized continuously into cash at each bar close.
            state.cash += (state.carry_perp_qty + state.dir_perp_qty) * dpx

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
                    if state.dir_perp_qty != 0.0:
                        dir_funding_accum += pnl_dir_funding
                    if state.carry_spot_qty != 0.0:
                        carry_funding_accum += pnl_carry_funding
            if state.carry_spot_qty != 0.0:
                carry_price_accum += pnl_carry_price

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
        raw_dir_perp_qty = dir_notional / price

        forced_dir_exit_price: float | None = None
        dir_exit_reason: str | None = None
        if dir_open:
            forced_dir_exit_price, dir_exit_reason = _directional_exit(
                side_qty=dir_entry_qty,
                entry_price=dir_entry_price,
                bars_held=i - dir_entry_idx,
                high=frame.high[i],
                low=frame.low[i],
                regime=regimes[i],
                decision=decision,
                config=sim_config,
            )
            dir_perp_qty = 0.0 if dir_exit_reason is not None else state.dir_perp_qty
            dir_notional = abs(dir_perp_qty * price)
        elif decision.directional_allowed and exp[i]:
            dir_perp_qty = raw_dir_perp_qty
        else:
            dir_perp_qty = 0.0
            dir_notional = 0.0

        target_spot_qty = carry_spot_qty
        target_carry_perp_qty = carry_perp_qty
        target_dir_perp_qty = dir_perp_qty
        target_perp_qty = target_carry_perp_qty + target_dir_perp_qty

        if _within_rebalance_threshold(
            state.carry_spot_qty, target_spot_qty, sim_config.carry_rebalance_threshold_pct
        ):
            target_spot_qty = state.carry_spot_qty
        if _within_rebalance_threshold(
            state.carry_perp_qty, target_carry_perp_qty, sim_config.carry_rebalance_threshold_pct
        ):
            target_carry_perp_qty = state.carry_perp_qty
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
            target_carry_perp_qty *= s
            target_dir_perp_qty *= s
            target_perp_qty = target_carry_perp_qty + target_dir_perp_qty
            carry_notional *= s
            dir_notional *= s

        pending_targets.append(
            PendingTarget(
                signal_idx=i,
                spot_qty=target_spot_qty,
                carry_perp_qty=target_carry_perp_qty,
                dir_perp_qty=target_dir_perp_qty,
            )
        )

        executable_target = (
            pending_targets.pop(0)
            if pending_targets
            and pending_targets[0].signal_idx + sim_config.order_latency_bars <= i
            else None
        )

        # Apply eligible orders using side-aware prices inside the execution candle range.
        prev_dir_qty = state.dir_perp_qty
        prev_carry_qty = state.carry_spot_qty
        last_spot_exec_price: float | None = None
        last_spot_exec_ts: datetime | None = None
        last_dir_exec_price: float | None = None
        last_dir_exec_ts: datetime | None = None
        last_carry_fee = 0.0
        last_carry_slip = 0.0
        last_dir_fee = 0.0
        last_dir_slip = 0.0
        if executable_target is None:
            spot_delta = 0.0
            carry_perp_delta = 0.0
            dir_perp_delta = 0.0
        else:
            executable_spot_qty = _clip_target_qty(executable_target.spot_qty, target_spot_qty)
            executable_carry_perp_qty = _clip_target_qty(
                executable_target.carry_perp_qty, target_carry_perp_qty
            )
            executable_dir_perp_qty = _clip_target_qty(
                executable_target.dir_perp_qty, target_dir_perp_qty
            )
            spot_delta = executable_spot_qty - state.carry_spot_qty
            carry_perp_delta = executable_carry_perp_qty - state.carry_perp_qty
            dir_perp_delta = executable_dir_perp_qty - state.dir_perp_qty

        spot_fill_price = _execution_price(
            frame=frame, idx=i, qty_delta=spot_delta, config=sim_config
        )
        exec_ts = _execution_ts(
            frame=frame,
            idx=i,
            timeframe_seconds=timeframe_seconds,
            config=sim_config,
        )

        fee, slip = _apply_trade(
            state=state,
            ts=exec_ts,
            leg="spot",
            source="carry",
            qty_delta=spot_delta,
            price=spot_fill_price,
            fee_model=fee_model,
            slippage_model=slippage_model,
            trades=trades,
        )
        if spot_delta != 0.0:
            last_spot_exec_price = spot_fill_price
            last_spot_exec_ts = exec_ts
            last_carry_fee += fee
            last_carry_slip += slip
        pnl_fees -= fee
        pnl_slip -= slip
        if spot_delta != 0.0:
            carry_fee_accum += fee
            carry_slip_accum += slip

        # Perp deltas: book as separate events for carry vs directional attribution.
        if carry_perp_delta != 0.0:
            carry_perp_fill_price = _execution_price(
                frame=frame, idx=i, qty_delta=carry_perp_delta, config=sim_config
            )
            fee, slip, mark_pnl = _apply_perp_trade(
                state=state,
                ts=exec_ts,
                source="carry",
                qty_delta=carry_perp_delta,
                fill_price=carry_perp_fill_price,
                mark_price=price,
                fee_model=fee_model,
                slippage_model=slippage_model,
                trades=trades,
            )
            pnl_price += mark_pnl
            pnl_carry_price += mark_pnl
            carry_price_accum += mark_pnl
            pnl_fees -= fee
            pnl_slip -= slip
            carry_fee_accum += fee
            carry_slip_accum += slip
            last_carry_fee += fee
            last_carry_slip += slip

        if dir_perp_delta != 0.0:
            dir_fill_price = (
                forced_dir_exit_price
                if forced_dir_exit_price is not None and dir_perp_delta * state.dir_perp_qty < 0.0
                else _execution_price(
                    frame=frame, idx=i, qty_delta=dir_perp_delta, config=sim_config
                )
            )
            fee, slip, mark_pnl = _apply_perp_trade(
                state=state,
                ts=exec_ts,
                source="directional",
                qty_delta=dir_perp_delta,
                fill_price=dir_fill_price,
                mark_price=price,
                fee_model=fee_model,
                slippage_model=slippage_model,
                trades=trades,
            )
            last_dir_exec_price = dir_fill_price
            last_dir_exec_ts = exec_ts
            pnl_price += mark_pnl
            pnl_dir_price += mark_pnl
            pnl_fees -= fee
            pnl_slip -= slip
            if prev_dir_qty != 0.0 or state.dir_perp_qty != 0.0:
                dir_fee_accum += fee
                dir_slip_accum += slip
            last_dir_fee += fee
            last_dir_slip += slip

        # Post-trade leverage enforcement: costs can reduce NAV enough to exceed cap.
        _post_trade_enforce_leverage(
            state=state,
            ts=exec_ts,
            frame=frame,
            idx=i,
            mark_price=price,
            leverage_cap=decision.leverage_cap_applied * (1.0 - sim_config.liquidation_buffer),
            fee_model=fee_model,
            slippage_model=slippage_model,
            sim_config=sim_config,
            timeframe_seconds=timeframe_seconds,
            trades=trades,
        )

        new_dir_qty = state.dir_perp_qty
        new_carry_qty = state.carry_spot_qty
        if not dir_open and prev_dir_qty == 0.0 and new_dir_qty != 0.0:
            dir_open = True
            dir_entry_ts = last_dir_exec_ts if last_dir_exec_ts is not None else exec_ts
            dir_entry_idx = i
            dir_entry_price = last_dir_exec_price if last_dir_exec_price is not None else price
            dir_entry_qty = new_dir_qty
            dir_entry_nav = _nav(state, price)
            dir_fee_accum = last_dir_fee
            dir_slip_accum = last_dir_slip
            dir_funding_accum = 0.0

        if dir_open and prev_dir_qty != 0.0 and new_dir_qty == 0.0:
            dir_exit_price = last_dir_exec_price if last_dir_exec_price is not None else price
            dir_exit_ts = last_dir_exec_ts if last_dir_exec_ts is not None else exec_ts
            pnl_price_trade = (dir_exit_price - dir_entry_price) * dir_entry_qty
            pnl_total = pnl_price_trade + dir_funding_accum - dir_fee_accum - dir_slip_accum
            side_label: Literal["long", "short"] = "long" if dir_entry_qty > 0 else "short"
            nav_exit = _nav(state, price)
            nav_delta = nav_exit - dir_entry_nav
            nav_delta_pct = None if dir_entry_nav == 0 else nav_delta / dir_entry_nav
            lifecycles.append(
                TradeLifecycle(
                    open_ts=dir_entry_ts,
                    close_ts=dir_exit_ts,
                    kind="directional",
                    side=side_label,
                    qty=abs(dir_entry_qty),
                    entry_price=dir_entry_price,
                    exit_price=dir_exit_price,
                    nav_entry=dir_entry_nav,
                    nav_exit=nav_exit,
                    nav_delta=nav_delta,
                    nav_delta_pct=nav_delta_pct,
                    pnl_price=pnl_price_trade,
                    pnl_funding=dir_funding_accum,
                    pnl_fees=dir_fee_accum,
                    pnl_slippage=dir_slip_accum,
                    pnl_total=pnl_total,
                    bars_held=i - dir_entry_idx,
                    exit_reason=dir_exit_reason or "target_flat",
                )
            )
            dir_open = False

        if (
            dir_open
            and prev_dir_qty != 0.0
            and new_dir_qty != 0.0
            and (prev_dir_qty > 0 > new_dir_qty or prev_dir_qty < 0 < new_dir_qty)
        ):
            dir_exit_price = last_dir_exec_price if last_dir_exec_price is not None else price
            dir_exit_ts = last_dir_exec_ts if last_dir_exec_ts is not None else exec_ts
            pnl_price_trade = (dir_exit_price - dir_entry_price) * dir_entry_qty
            pnl_total = pnl_price_trade + dir_funding_accum - dir_fee_accum - dir_slip_accum
            side_label2: Literal["long", "short"] = "long" if dir_entry_qty > 0 else "short"
            nav_exit = _nav(state, price)
            nav_delta = nav_exit - dir_entry_nav
            nav_delta_pct = None if dir_entry_nav == 0 else nav_delta / dir_entry_nav
            lifecycles.append(
                TradeLifecycle(
                    open_ts=dir_entry_ts,
                    close_ts=dir_exit_ts,
                    kind="directional",
                    side=side_label2,
                    qty=abs(dir_entry_qty),
                    entry_price=dir_entry_price,
                    exit_price=dir_exit_price,
                    nav_entry=dir_entry_nav,
                    nav_exit=nav_exit,
                    nav_delta=nav_delta,
                    nav_delta_pct=nav_delta_pct,
                    pnl_price=pnl_price_trade,
                    pnl_funding=dir_funding_accum,
                    pnl_fees=dir_fee_accum,
                    pnl_slippage=dir_slip_accum,
                    pnl_total=pnl_total,
                    bars_held=i - dir_entry_idx,
                    exit_reason=dir_exit_reason or "flip",
                )
            )
            dir_entry_ts = last_dir_exec_ts if last_dir_exec_ts is not None else exec_ts
            dir_entry_idx = i
            dir_entry_price = last_dir_exec_price if last_dir_exec_price is not None else price
            dir_entry_qty = new_dir_qty
            dir_entry_nav = _nav(state, price)
            dir_fee_accum = last_dir_fee
            dir_slip_accum = last_dir_slip
            dir_funding_accum = 0.0

        if not carry_open and abs(prev_carry_qty) <= 1e-12 and abs(new_carry_qty) > 1e-12:
            carry_open = True
            carry_entry_ts = last_spot_exec_ts if last_spot_exec_ts is not None else exec_ts
            carry_entry_idx = i
            carry_entry_price = last_spot_exec_price if last_spot_exec_price is not None else price
            carry_entry_qty = new_carry_qty
            carry_entry_nav = _nav(state, price)
            carry_fee_accum = last_carry_fee
            carry_slip_accum = last_carry_slip
            carry_price_accum = 0.0
            carry_funding_accum = 0.0

        if carry_open and abs(prev_carry_qty) > 1e-12 and abs(new_carry_qty) <= 1e-12:
            carry_exit_price = last_spot_exec_price if last_spot_exec_price is not None else price
            carry_exit_ts = last_spot_exec_ts if last_spot_exec_ts is not None else exec_ts
            pnl_total = carry_price_accum + carry_funding_accum - carry_fee_accum - carry_slip_accum
            nav_exit = _nav(state, price)
            nav_delta = nav_exit - carry_entry_nav
            nav_delta_pct = None if carry_entry_nav == 0 else nav_delta / carry_entry_nav
            lifecycles.append(
                TradeLifecycle(
                    open_ts=carry_entry_ts,
                    close_ts=carry_exit_ts,
                    kind="carry",
                    side="carry",
                    qty=abs(carry_entry_qty),
                    entry_price=carry_entry_price,
                    exit_price=carry_exit_price,
                    nav_entry=carry_entry_nav,
                    nav_exit=nav_exit,
                    nav_delta=nav_delta,
                    nav_delta_pct=nav_delta_pct,
                    pnl_price=carry_price_accum,
                    pnl_funding=carry_funding_accum,
                    pnl_fees=carry_fee_accum,
                    pnl_slippage=carry_slip_accum,
                    pnl_total=pnl_total,
                    bars_held=i - carry_entry_idx,
                    exit_reason="target_flat",
                )
            )
            carry_open = False

        if carry_open and regimes[i] != prev_regime:
            pnl_total = carry_price_accum + carry_funding_accum - carry_fee_accum - carry_slip_accum
            nav_exit = _nav(state, price)
            nav_delta = nav_exit - carry_entry_nav
            nav_delta_pct = None if carry_entry_nav == 0 else nav_delta / carry_entry_nav
            lifecycles.append(
                TradeLifecycle(
                    open_ts=carry_entry_ts,
                    close_ts=ts,
                    kind="carry",
                    side="carry",
                    qty=abs(carry_entry_qty),
                    entry_price=carry_entry_price,
                    exit_price=price,
                    nav_entry=carry_entry_nav,
                    nav_exit=nav_exit,
                    nav_delta=nav_delta,
                    nav_delta_pct=nav_delta_pct,
                    pnl_price=carry_price_accum,
                    pnl_funding=carry_funding_accum,
                    pnl_fees=carry_fee_accum,
                    pnl_slippage=carry_slip_accum,
                    pnl_total=pnl_total,
                    bars_held=i - carry_entry_idx,
                    exit_reason="regime_change",
                )
            )
            carry_entry_ts = ts
            carry_entry_idx = i
            carry_entry_price = price
            carry_entry_qty = new_carry_qty
            carry_entry_nav = _nav(state, price)
            carry_fee_accum = 0.0
            carry_slip_accum = 0.0
            carry_price_accum = 0.0
            carry_funding_accum = 0.0

        nav_after = _nav(state, price)
        gross = _gross_exposure(state, price)
        leverage = gross / nav_after if nav_after > 0 else 0.0

        bars.append(
            BarResult(
                ts=ts,
                price=price,
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
        prev_regime = regimes[i]

    return SimulationResult(bars=bars, trades=trades, lifecycles=lifecycles)


def _post_trade_enforce_leverage(
    *,
    state: PortfolioState,
    ts: datetime,
    frame: OHLCVFrame,
    idx: int,
    mark_price: float,
    leverage_cap: float,
    fee_model: FeeModel,
    slippage_model: SlippageModel,
    sim_config: SimulatorConfig,
    timeframe_seconds: int,
    trades: list[TradeEvent],
) -> None:
    for _ in range(8):
        nav = _nav(state, mark_price)
        gross = _gross_exposure(state, mark_price)
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
            spot_fill_price = _execution_price(
                frame=frame, idx=idx, qty_delta=spot_delta, config=sim_config
            )
            spot_exec_ts = _execution_ts(
                frame=frame,
                idx=idx,
                timeframe_seconds=timeframe_seconds,
                config=sim_config,
            )
            _apply_trade(
                state=state,
                ts=spot_exec_ts,
                leg="spot",
                source="carry",
                qty_delta=spot_delta,
                price=spot_fill_price,
                fee_model=fee_model,
                slippage_model=slippage_model,
                trades=trades,
            )

        carry_perp_delta = target_carry_perp - state.carry_perp_qty
        if carry_perp_delta != 0.0:
            carry_perp_fill_price = _execution_price(
                frame=frame, idx=idx, qty_delta=carry_perp_delta, config=sim_config
            )
            carry_perp_exec_ts = _execution_ts(
                frame=frame,
                idx=idx,
                timeframe_seconds=timeframe_seconds,
                config=sim_config,
            )
            _apply_perp_trade(
                state=state,
                ts=carry_perp_exec_ts,
                source="carry",
                qty_delta=carry_perp_delta,
                fill_price=carry_perp_fill_price,
                mark_price=mark_price,
                fee_model=fee_model,
                slippage_model=slippage_model,
                trades=trades,
            )

        dir_perp_delta = target_dir_perp - state.dir_perp_qty
        if dir_perp_delta != 0.0:
            dir_fill_price = _execution_price(
                frame=frame, idx=idx, qty_delta=dir_perp_delta, config=sim_config
            )
            dir_exec_ts = _execution_ts(
                frame=frame,
                idx=idx,
                timeframe_seconds=timeframe_seconds,
                config=sim_config,
            )
            _apply_perp_trade(
                state=state,
                ts=dir_exec_ts,
                source="directional",
                qty_delta=dir_perp_delta,
                fill_price=dir_fill_price,
                mark_price=mark_price,
                fee_model=fee_model,
                slippage_model=slippage_model,
                trades=trades,
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
