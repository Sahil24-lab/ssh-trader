from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

from ssh_trader.backtest.simulator import FeeModel, SimulatorConfig, SlippageModel
from ssh_trader.control.engine import ControlConfig
from ssh_trader.guidance.policy import (
    GuidancePolicy,
    GuidancePolicyConfig,
    allocation_band_from_config,
)
from ssh_trader.live.hyperliquid_stub import HyperliquidStubConfig
from ssh_trader.nav.compression import CompressionConfig
from ssh_trader.nav.regime import RegimeConfig
from ssh_trader.risk.governor import RiskConfig, RiskGovernor


def load_json_config(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return cast(dict[str, object], data)


def _section(cfg: dict[str, object], key: str) -> dict[str, Any]:
    obj = cfg.get(key, {})
    return cast(dict[str, Any], obj) if isinstance(obj, dict) else {}


def build_guidance_policy(cfg: dict[str, object]) -> GuidancePolicy:
    guidance_cfg = _section(cfg, "guidance")
    defaults = GuidancePolicyConfig()
    return GuidancePolicy(
        GuidancePolicyConfig(
            risk_off_carry=allocation_band_from_config(
                guidance_cfg.get("risk_off_carry"), defaults.risk_off_carry
            ),
            risk_off_directional=allocation_band_from_config(
                guidance_cfg.get("risk_off_directional"), defaults.risk_off_directional
            ),
            neutral_carry=allocation_band_from_config(
                guidance_cfg.get("neutral_carry"), defaults.neutral_carry
            ),
            neutral_directional=allocation_band_from_config(
                guidance_cfg.get("neutral_directional"), defaults.neutral_directional
            ),
            risk_on_carry=allocation_band_from_config(
                guidance_cfg.get("risk_on_carry"), defaults.risk_on_carry
            ),
            risk_on_directional=allocation_band_from_config(
                guidance_cfg.get("risk_on_directional"), defaults.risk_on_directional
            ),
            aggressiveness=float(guidance_cfg.get("aggressiveness", defaults.aggressiveness)),
        )
    )


def build_risk_governor(
    cfg: dict[str, object], *, default_kill_switch_action: Literal["carry_only", "flat"]
) -> RiskGovernor:
    risk_cfg = _section(cfg, "risk")
    kill_action_raw = risk_cfg.get("kill_switch_action", default_kill_switch_action)
    if not isinstance(kill_action_raw, str):
        raise ValueError("kill_switch_action must be a string")
    if kill_action_raw not in ("carry_only", "flat"):
        raise ValueError("kill_switch_action must be 'carry_only' or 'flat'")
    kill_action = cast(Literal["carry_only", "flat"], kill_action_raw)
    return RiskGovernor(
        RiskConfig(
            leverage_cap=float(risk_cfg.get("leverage_cap", 1.5)),
            venue_cap_frac=float(risk_cfg.get("venue_cap_frac", 0.30)),
            max_drawdown=float(risk_cfg.get("max_drawdown", 0.20)),
            kill_switch_action=kill_action,
            vol_spike_vol_pct=float(risk_cfg.get("vol_spike_vol_pct", 0.90)),
        )
    )


def build_nav_config(cfg: dict[str, object]) -> RegimeConfig:
    nav_cfg = _section(cfg, "nav")
    return RegimeConfig(
        long_ma_window=int(nav_cfg.get("long_ma_window", 200)),
        trend_method=cast(str, nav_cfg.get("trend_method", "sma")),
        trend_span=int(nav_cfg.get("trend_span", 200)),
        trend_band=float(nav_cfg.get("trend_band", 0.0)),
        rv_window=int(nav_cfg.get("rv_window", 20)),
        vol_percentile_window=int(nav_cfg.get("vol_percentile_window", 252)),
        annualization_factor=float(nav_cfg.get("annualization_factor", 1.0)),
        risk_on_vol_pct_max=float(nav_cfg.get("risk_on_vol_pct_max", 0.7)),
        risk_off_vol_pct_min=float(nav_cfg.get("risk_off_vol_pct_min", 0.9)),
        risk_on_exit_vol_pct=float(nav_cfg.get("risk_on_exit_vol_pct", 0.8)),
        risk_off_exit_vol_pct=float(nav_cfg.get("risk_off_exit_vol_pct", 0.8)),
        confirm_bars=int(nav_cfg.get("confirm_bars", 3)),
        funding_mode=cast(str, nav_cfg.get("funding_mode", "sign")),
    )


def build_compression_config(cfg: dict[str, object]) -> CompressionConfig:
    comp_cfg = _section(cfg, "compression")
    return CompressionConfig(
        atr_window=int(comp_cfg.get("atr_window", 14)),
        contraction_lookback=int(comp_cfg.get("contraction_lookback", 50)),
        vol_pct_window=int(comp_cfg.get("vol_pct_window", 252)),
        range_window=int(comp_cfg.get("range_window", 50)),
        weight_atr=float(comp_cfg.get("weight_atr", 1.0)),
        weight_range=float(comp_cfg.get("weight_range", 1.0)),
        weight_vol=float(comp_cfg.get("weight_vol", 1.0)),
        vol_pct_low_threshold=float(comp_cfg.get("vol_pct_low_threshold", 0.35)),
        score_trigger=float(comp_cfg.get("score_trigger", 0.6)),
        breakout_confirm=int(comp_cfg.get("breakout_confirm", 1)),
        vol_expand_threshold=float(comp_cfg.get("vol_expand_threshold", 0.6)),
    )


def build_simulator_config(
    cfg: dict[str, object], *, initial_nav_override: float | None = None
) -> SimulatorConfig:
    sim_cfg = _section(cfg, "sim")
    initial_nav = (
        float(initial_nav_override)
        if initial_nav_override is not None
        else float(sim_cfg.get("initial_nav", 1_000_000.0))
    )
    return SimulatorConfig(
        initial_nav=initial_nav,
        carry_funding_freq_hours=int(sim_cfg.get("carry_funding_freq_hours", 8)),
        liquidation_buffer=float(sim_cfg.get("liquidation_buffer", 0.10)),
        target_dir_vol=float(sim_cfg.get("target_dir_vol", 0.20)),
        min_dir_vol=float(sim_cfg.get("min_dir_vol", 1e-6)),
        order_latency_bars=int(sim_cfg.get("order_latency_bars", 1)),
        fill_range_position=float(sim_cfg.get("fill_range_position", 0.75)),
        fill_time_fraction=float(sim_cfg.get("fill_time_fraction", 0.25)),
        directional_stop_loss_pct=float(sim_cfg.get("directional_stop_loss_pct", 0.02)),
        directional_take_profit_pct=float(sim_cfg.get("directional_take_profit_pct", 0.04)),
        directional_max_hold_bars=int(sim_cfg.get("directional_max_hold_bars", 24)),
        carry_rebalance_threshold_pct=float(sim_cfg.get("carry_rebalance_threshold_pct", 0.01)),
    )


def build_fee_model(cfg: dict[str, object]) -> FeeModel:
    fees_cfg = _section(cfg, "fees")
    return FeeModel(taker_fee_bps=float(fees_cfg.get("taker_fee_bps", 5.0)))


def build_slippage_model(cfg: dict[str, object]) -> SlippageModel:
    fees_cfg = _section(cfg, "fees")
    return SlippageModel(
        slippage_bps_at_1x_nav=float(fees_cfg.get("slippage_bps_at_1x_nav", 10.0))
    )


def build_control_config(cfg: dict[str, object], *, default_symbol: str = "BTC-PERP") -> ControlConfig:
    control_cfg = _section(cfg, "control")
    return ControlConfig(
        symbol=cast(str, control_cfg.get("symbol", default_symbol)),
        rebalance_interval_bars=int(control_cfg.get("rebalance_interval_bars", 1)),
        max_slippage_bps=float(control_cfg.get("max_slippage_bps", 30.0)),
        min_order_qty=float(control_cfg.get("min_order_qty", 0.0)),
        oracle_divergence_bps=float(control_cfg.get("oracle_divergence_bps", 50.0)),
        mev_mode=cast(str, control_cfg.get("mev_mode", "placeholder")),
    )


def build_hyperliquid_stub_config(
    cfg: dict[str, object], *, default_symbol: str = "BTC-PERP", default_equity: float = 1_000_000.0
) -> HyperliquidStubConfig:
    live_cfg = _section(cfg, "live")
    return HyperliquidStubConfig(
        symbol=cast(str, live_cfg.get("symbol", default_symbol)),
        venue=cast(str, live_cfg.get("venue", "hyperliquid_stub")),
        latency_ms=int(live_cfg.get("latency_ms", 0)),
        apply_latency=bool(live_cfg.get("apply_latency", False)),
        slippage_bps_at_1x_notional=float(live_cfg.get("slippage_bps_at_1x_notional", 10.0)),
        max_fill_ratio=float(live_cfg.get("max_fill_ratio", 1.0)),
        initial_mark_price=float(live_cfg.get("initial_mark_price", 50_000.0)),
        initial_funding_rate=float(live_cfg.get("initial_funding_rate", 0.0)),
        initial_equity=float(live_cfg.get("initial_equity", default_equity)),
        maintenance_margin_ratio=float(live_cfg.get("maintenance_margin_ratio", 0.05)),
    )
