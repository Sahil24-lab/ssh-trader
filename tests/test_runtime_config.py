from __future__ import annotations

from ssh_trader.config.runtime import (
    build_control_config,
    build_hyperliquid_stub_config,
    build_nav_config,
    build_risk_governor,
)


def test_runtime_builders_apply_shared_overrides() -> None:
    cfg: dict[str, object] = {
        "risk": {
            "leverage_cap": 1.1,
            "venue_cap_frac": 0.2,
            "max_drawdown": 0.15,
            "kill_switch_action": "flat",
            "vol_spike_vol_pct": 0.8,
        },
        "nav": {
            "long_ma_window": 150,
            "rv_window": 10,
            "vol_percentile_window": 100,
            "confirm_bars": 2,
            "funding_mode": "ignore",
        },
        "control": {
            "symbol": "ETH-PERP",
            "min_order_qty": 0.01,
            "rebalance_interval_bars": 2,
        },
        "live": {
            "symbol": "ETH-PERP",
            "initial_equity": 25_000.0,
        },
    }

    risk = build_risk_governor(cfg, default_kill_switch_action="carry_only")
    nav = build_nav_config(cfg)
    control = build_control_config(cfg)
    venue = build_hyperliquid_stub_config(cfg)

    assert risk.config.leverage_cap == 1.1
    assert risk.config.kill_switch_action == "flat"
    assert nav.long_ma_window == 150
    assert nav.funding_mode == "ignore"
    assert control.symbol == "ETH-PERP"
    assert control.min_order_qty == 0.01
    assert venue.symbol == "ETH-PERP"
    assert venue.initial_equity == 25_000.0
