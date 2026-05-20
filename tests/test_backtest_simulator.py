from datetime import datetime, timedelta, timezone

from ssh_trader.backtest.simulator import FeeModel, SimulatorConfig, SlippageModel, simulate_portfolio
from ssh_trader.config.runtime import build_guidance_policy
from ssh_trader.data.model import OHLCVFrame
from ssh_trader.guidance.policy import GuidancePolicy, GuidancePolicyConfig
from ssh_trader.nav.compression import CompressionConfig
from ssh_trader.nav.regime import RegimeConfig
from ssh_trader.risk.governor import RiskConfig, RiskGovernor


def _frame(close: list[float], funding: list[float] | None = None) -> OHLCVFrame:
    ts0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
    ts = [ts0 + timedelta(hours=i) for i in range(len(close))]
    high = [c * 1.01 for c in close]
    low = [c * 0.99 for c in close]
    open_ = close[:]
    vol = [1.0] * len(close)
    return OHLCVFrame(
        ts=ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=vol,
        funding=funding,
    )


def test_simulator_enforces_leverage_cap_and_funding_accrues() -> None:
    close = [100.0] * 5 + [101.0, 102.0, 103.0, 104.0, 105.0]
    funding = [0.0] + [0.001] * (len(close) - 1)
    frame = _frame(close, funding=funding)

    guidance = GuidancePolicy(GuidancePolicyConfig(aggressiveness=1.0))
    risk = RiskGovernor(RiskConfig(venue_cap_frac=1.0, leverage_cap=1.5, max_drawdown=0.5))

    nav_cfg = RegimeConfig(
        trend_method="sma",
        long_ma_window=2,
        rv_window=2,
        vol_percentile_window=2,
        confirm_bars=1,
        risk_on_vol_pct_max=1.0,
        risk_off_vol_pct_min=1.0,
    )
    comp_cfg = CompressionConfig(
        atr_window=2,
        contraction_lookback=3,
        vol_pct_window=2,
        range_window=3,
        breakout_confirm=1,
        score_trigger=1e-6,
        vol_expand_threshold=1e-6,
        vol_pct_low_threshold=1.0,
    )
    sim_cfg = SimulatorConfig(
        initial_nav=10_000.0,
        carry_funding_freq_hours=1,
        liquidation_buffer=0.0,
        order_latency_bars=0,
        fill_range_position=0.5,
    )

    result = simulate_portfolio(
        frame=frame,
        guidance=guidance,
        risk=risk,
        nav_config=nav_cfg,
        compression_config=comp_cfg,
        sim_config=sim_cfg,
    )
    assert result.bars
    assert all(b.leverage <= 1.5 + 1e-9 for b in result.bars)
    assert sum(b.pnl_funding for b in result.bars) > 0.0


def test_kill_switch_disables_directional_after_drawdown() -> None:
    # Construct a simple "risk-on + breakout" window, then a crash.
    # This should enable directional briefly and then trigger the drawdown kill switch.
    close = [100.0, 103.0, 104.5, 105.6, 60.0, 59.0, 58.0]
    frame = _frame(close, funding=[0.0] * len(close))

    guidance = GuidancePolicy(GuidancePolicyConfig(aggressiveness=1.0))
    risk = RiskGovernor(
        RiskConfig(
            venue_cap_frac=1.0, leverage_cap=1.5, max_drawdown=0.05, kill_switch_action="carry_only"
        )
    )

    nav_cfg = RegimeConfig(
        trend_method="sma",
        long_ma_window=2,
        rv_window=1,
        vol_percentile_window=3,
        confirm_bars=1,
        risk_on_vol_pct_max=1.0,
        risk_off_vol_pct_min=1.0,
        funding_mode="ignore",
    )
    comp_cfg = CompressionConfig(
        atr_window=1,
        contraction_lookback=1,
        vol_pct_window=3,
        vol_pct_low_threshold=1.0,
        weight_atr=0.0,
        weight_range=0.0,
        weight_vol=1.0,
        range_window=1,
        breakout_confirm=1,
        score_trigger=1e-6,
        vol_expand_threshold=1e-6,
    )
    sim_cfg = SimulatorConfig(
        initial_nav=10_000.0,
        carry_funding_freq_hours=1,
        liquidation_buffer=0.0,
        order_latency_bars=0,
        fill_range_position=0.5,
    )

    result = simulate_portfolio(
        frame=frame,
        guidance=guidance,
        risk=risk,
        nav_config=nav_cfg,
        compression_config=comp_cfg,
        sim_config=sim_cfg,
    )
    assert any(b.kill_switch_active for b in result.bars)

    # After kill switch, directional notional should be zero (carry-only mode).
    idx = next(i for i, b in enumerate(result.bars) if b.kill_switch_active)
    assert all(b.directional_notional == 0.0 for b in result.bars[idx:])


def test_leverage_scaling_keeps_carry_spot_and_perp_in_sync() -> None:
    frame = _frame([100.0] * 8, funding=[0.0] * 8)
    guidance = GuidancePolicy(GuidancePolicyConfig(aggressiveness=1.0))
    risk = RiskGovernor(RiskConfig(venue_cap_frac=1.0, leverage_cap=0.5, max_drawdown=0.5))
    nav_cfg = RegimeConfig(
        trend_method="sma",
        long_ma_window=2,
        rv_window=2,
        vol_percentile_window=2,
        confirm_bars=1,
        risk_on_vol_pct_max=1.0,
        risk_off_vol_pct_min=1.0,
    )
    comp_cfg = CompressionConfig(
        atr_window=2,
        contraction_lookback=3,
        vol_pct_window=2,
        range_window=3,
        breakout_confirm=1,
        score_trigger=1e-6,
        vol_expand_threshold=1e-6,
        vol_pct_low_threshold=1.0,
    )

    result = simulate_portfolio(
        frame=frame,
        guidance=guidance,
        risk=risk,
        nav_config=nav_cfg,
        compression_config=comp_cfg,
        sim_config=SimulatorConfig(
            initial_nav=10_000.0,
            carry_funding_freq_hours=1,
            liquidation_buffer=0.0,
        ),
    )

    carry_trades = [t for t in result.trades if t.source == "carry"]
    first_spot = next(t for t in carry_trades if t.leg == "spot")
    first_perp = next(t for t in carry_trades if t.leg == "perp")
    assert abs(first_spot.qty_delta) == abs(first_perp.qty_delta)


def test_simulator_fills_after_latency_inside_candle_range() -> None:
    frame = _frame([100.0] * 4, funding=[0.0] * 4)
    frame.high[:] = [120.0] * 4
    frame.low[:] = [80.0] * 4
    guidance = GuidancePolicy(GuidancePolicyConfig(aggressiveness=1.0))
    risk = RiskGovernor(RiskConfig(venue_cap_frac=1.0, leverage_cap=1.5, max_drawdown=0.5))

    result = simulate_portfolio(
        frame=frame,
        guidance=guidance,
        risk=risk,
        fee_model=FeeModel(taker_fee_bps=0.0),
        slippage_model=SlippageModel(slippage_bps_at_1x_nav=0.0),
        sim_config=SimulatorConfig(
            initial_nav=10_000.0,
            carry_funding_freq_hours=1,
            liquidation_buffer=0.0,
            order_latency_bars=1,
            fill_range_position=0.75,
            fill_time_fraction=0.25,
        ),
    )

    first_spot = next(t for t in result.trades if t.leg == "spot")
    first_perp = next(t for t in result.trades if t.leg == "perp" and t.source == "carry")
    assert first_spot.ts == frame.ts[1] + timedelta(minutes=15)
    assert first_perp.ts == frame.ts[1] + timedelta(minutes=15)
    assert first_spot.price == 110.0
    assert first_perp.price == 90.0


def test_guidance_config_can_disable_carry() -> None:
    guidance = build_guidance_policy(
        {
            "guidance": {
                "aggressiveness": 1.0,
                "risk_off_carry": [0.0, 0.0],
                "neutral_carry": [0.0, 0.0],
                "risk_on_carry": [0.0, 0.0],
            }
        }
    )
    frame = _frame([100.0] * 5, funding=[0.0] * 5)
    result = simulate_portfolio(
        frame=frame,
        guidance=guidance,
        risk=RiskGovernor(RiskConfig(venue_cap_frac=1.0, leverage_cap=1.5, max_drawdown=0.5)),
        fee_model=FeeModel(taker_fee_bps=0.0),
        slippage_model=SlippageModel(slippage_bps_at_1x_nav=0.0),
        sim_config=SimulatorConfig(initial_nav=10_000.0, carry_funding_freq_hours=1),
    )
    assert not [t for t in result.trades if t.source == "carry"]


def test_directional_position_persists_until_take_profit() -> None:
    close = [100.0, 101.0, 102.0, 103.0, 104.0, 106.0]
    frame = _frame(close, funding=[0.0] * len(close))
    frame.high[:] = [c + 0.5 for c in close]
    frame.low[:] = [c - 0.5 for c in close]
    frame.high[4] = 108.0
    guidance = GuidancePolicy(GuidancePolicyConfig(aggressiveness=1.0))
    risk = RiskGovernor(RiskConfig(venue_cap_frac=1.0, leverage_cap=1.5, max_drawdown=0.5))
    nav_cfg = RegimeConfig(
        trend_method="sma",
        long_ma_window=2,
        rv_window=1,
        vol_percentile_window=2,
        confirm_bars=1,
        risk_on_vol_pct_max=1.0,
        risk_off_vol_pct_min=1.0,
        funding_mode="ignore",
    )
    comp_cfg = CompressionConfig(
        atr_window=1,
        contraction_lookback=1,
        vol_pct_window=2,
        vol_pct_low_threshold=1.0,
        weight_atr=0.0,
        weight_range=0.0,
        weight_vol=1.0,
        range_window=1,
        breakout_confirm=1,
        score_trigger=1e-6,
        vol_expand_threshold=1e-6,
    )
    result = simulate_portfolio(
        frame=frame,
        guidance=guidance,
        risk=risk,
        nav_config=nav_cfg,
        compression_config=comp_cfg,
        fee_model=FeeModel(taker_fee_bps=0.0),
        slippage_model=SlippageModel(slippage_bps_at_1x_nav=0.0),
        sim_config=SimulatorConfig(
            initial_nav=10_000.0,
            carry_funding_freq_hours=1,
            order_latency_bars=0,
            fill_range_position=0.5,
            directional_stop_loss_pct=0.02,
            directional_take_profit_pct=0.03,
            directional_max_hold_bars=10,
        ),
    )
    directional = [t for t in result.lifecycles if t.kind == "directional"]
    assert directional
    assert directional[0].bars_held > 1
    assert directional[0].exit_reason == "take_profit"
