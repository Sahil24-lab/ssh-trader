from datetime import datetime, timezone

from ssh_trader.control.engine import ControlConfig, ControlEngine, TargetExposure
from ssh_trader.live.hyperliquid_stub import HyperliquidStubAdapter, HyperliquidStubConfig
from ssh_trader.risk.governor import RiskConfig, RiskGovernor


def _engine() -> ControlEngine:
    venue = HyperliquidStubAdapter(
        HyperliquidStubConfig(
            symbol="BTC-PERP",
            initial_mark_price=100.0,
            initial_equity=10_000.0,
            max_fill_ratio=0.5,
        )
    )
    risk = RiskGovernor(
        RiskConfig(
            leverage_cap=1.5,
            venue_cap_frac=1.0,
            max_drawdown=0.2,
            vol_spike_vol_pct=0.8,
        )
    )
    return ControlEngine(
        venue=venue,
        risk=risk,
        config=ControlConfig(
            symbol="BTC-PERP",
            rebalance_interval_bars=1,
            max_slippage_bps=100.0,
            min_order_qty=0.0,
            oracle_divergence_bps=20.0,
        ),
    )


def test_oracle_divergence_refuses_order() -> None:
    engine = _engine()
    out = engine.on_bar(
        ts=datetime.now(tz=timezone.utc),
        target=TargetExposure(target_perp_qty=1.0, directional_requested=True),
        regime_state="RISK_ON",
        oracle_price=80.0,
        vol_pct=0.2,
        vol_spike_active=False,
    )
    assert out.skipped is True
    assert out.reason == "oracle_divergence"


def test_partial_fill_sets_pending_qty() -> None:
    engine = _engine()
    ts = datetime.now(tz=timezone.utc)
    out1 = engine.on_bar(
        ts=ts,
        target=TargetExposure(target_perp_qty=2.0, directional_requested=True),
        regime_state="RISK_ON",
        oracle_price=100.0,
        vol_pct=0.2,
        vol_spike_active=False,
    )
    assert out1.skipped is False
    assert out1.hypothetical_fill is not None
    assert out1.hypothetical_fill.status == "partial"

    out2 = engine.on_bar(
        ts=ts,
        target=TargetExposure(target_perp_qty=2.0, directional_requested=True),
        regime_state="RISK_ON",
        oracle_price=100.0,
        vol_pct=0.2,
        vol_spike_active=False,
    )
    assert out2.skipped is False
    assert out2.hypothetical_fill is not None
