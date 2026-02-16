from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ssh_trader.control.engine import ControlConfig, ControlDecision, ControlEngine, TargetExposure
from ssh_trader.data.clean import fill_missing_intervals, normalize_and_sort
from ssh_trader.data.io_csv import load_ohlcv_csv
from ssh_trader.data.model import OHLCVFrame, parse_timeframe
from ssh_trader.guidance.policy import GuidancePolicy, GuidancePolicyConfig
from ssh_trader.nav.compression import CompressionConfig, compression_score, expansion_trigger
from ssh_trader.nav.features import trend_signal, volatility_features_from_close
from ssh_trader.nav.regime import Regime, RegimeConfig, classify_regimes
from ssh_trader.risk.governor import RiskConfig, RiskGovernor

from .hyperliquid_stub import HyperliquidStubAdapter, HyperliquidStubConfig


@dataclass(frozen=True, slots=True)
class ShadowRunnerConfig:
    symbol: str = "BTC-PERP"
    target_directional_vol: float = 0.20
    min_realized_vol: float = 1e-6
    vol_spike_threshold: float = 0.90


def run_shadow(
    frame: OHLCVFrame, *, config: ShadowRunnerConfig | None = None
) -> list[dict[str, str]]:
    cfg = config if config is not None else ShadowRunnerConfig()
    nav_cfg = RegimeConfig()
    comp_cfg = CompressionConfig()
    guidance = GuidancePolicy(GuidancePolicyConfig(aggressiveness=0.5))
    risk = RiskGovernor(RiskConfig())
    venue = HyperliquidStubAdapter(HyperliquidStubConfig(symbol=cfg.symbol))
    control = ControlEngine(
        venue=venue,
        risk=risk,
        config=ControlConfig(
            symbol=cfg.symbol,
            rebalance_interval_bars=1,
            max_slippage_bps=30.0,
            oracle_divergence_bps=50.0,
        ),
    )

    regimes = classify_regimes(
        close=frame.close,
        high=frame.high,
        low=frame.low,
        funding=frame.funding,
        config=nav_cfg,
        initial=Regime.NEUTRAL,
    )
    vol_feats = volatility_features_from_close(
        close=frame.close,
        rv_window=nav_cfg.rv_window,
        vol_percentile_window=nav_cfg.vol_percentile_window,
        annualization_factor=nav_cfg.annualization_factor,
    )
    trend = trend_signal(
        close=frame.close,
        method=nav_cfg.trend_method,
        window_or_span=(
            nav_cfg.long_ma_window if nav_cfg.trend_method == "sma" else nav_cfg.trend_span
        ),
        band=nav_cfg.trend_band,
    )
    comp_score, _ = compression_score(
        high=frame.high, low=frame.low, close=frame.close, config=comp_cfg
    )
    exp = expansion_trigger(
        close=frame.close,
        high=frame.high,
        low=frame.low,
        vol_pct=vol_feats.vol_percentile,
        trend=trend,
        score=comp_score,
        config=comp_cfg,
    )

    logs: list[dict[str, str]] = []
    for i, ts in enumerate(frame.ts):
        mark = frame.close[i]
        funding = frame.funding[i] if frame.funding is not None else 0.0
        venue.set_market(mark_price=mark, funding_rate=funding)

        margin = venue.get_margin_status()
        target_alloc = guidance.targets(regimes[i])
        dir_vol = vol_feats.realized_vol[i]
        vol_scale = 0.0
        if dir_vol is not None:
            vol_scale = min(1.0, cfg.target_directional_vol / max(cfg.min_realized_vol, dir_vol))
        directional_enabled = regimes[i] == Regime.RISK_ON and exp[i]
        target_notional = margin.equity * target_alloc.directional_frac * vol_scale
        target_qty = (target_notional / mark) if directional_enabled and mark > 0 else 0.0
        vol_pct_i = vol_feats.vol_percentile[i]
        vol_spike_active = vol_pct_i is not None and vol_pct_i >= cfg.vol_spike_threshold

        decision: ControlDecision = control.on_bar(
            ts=ts,
            target=TargetExposure(
                target_perp_qty=target_qty,
                directional_requested=directional_enabled,
            ),
            regime_state=regimes[i].value,
            oracle_price=mark,
            vol_pct=vol_pct_i,
            vol_spike_active=vol_spike_active,
        )

        intended = ""
        hypo_fill = ""
        if decision.intended_order is not None:
            intended = f"{decision.intended_order.side}:{decision.intended_order.quantity:.6f}"
        if decision.hypothetical_fill is not None:
            hypo_fill = (
                f"{decision.hypothetical_fill.status}:"
                f"{decision.hypothetical_fill.filled_qty:.6f}@"
                f"{decision.hypothetical_fill.fill_price:.2f}"
            )

        logs.append(
            {
                "timestamp": ts.isoformat().replace("+00:00", "Z"),
                "regime": regimes[i].value,
                "intended_order": intended,
                "hypothetical_fill": hypo_fill,
                "slippage_estimate_bps": f"{decision.slippage_estimate_bps:.6f}",
                "skipped": "1" if decision.skipped else "0",
                "reason": decision.reason or "",
                "route_hint": decision.route_hint,
            }
        )

    return logs


def _load_cfg(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return cast(dict[str, object], data)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run live shadow mode without order signing.")
    p.add_argument("--csv", required=True, type=Path, help="OHLCV CSV path.")
    p.add_argument("--config", type=Path, default=None, help="Optional JSON config.")
    p.add_argument("--timeframe", type=str, default=None, help="Expected timeframe, e.g. 1h.")
    p.add_argument(
        "--fill-missing", action="store_true", help="Fill missing intervals deterministically."
    )
    p.add_argument(
        "--output", type=Path, default=Path("shadow_log.csv"), help="CSV output for shadow logs."
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = _load_cfg(args.config)

    frame = load_ohlcv_csv(args.csv)
    frame, _ = normalize_and_sort(frame)

    data_cfg_obj = cfg.get("data", {})
    data_cfg: dict[str, Any] = (
        cast(dict[str, Any], data_cfg_obj) if isinstance(data_cfg_obj, dict) else {}
    )
    tf = args.timeframe or cast(str | None, data_cfg.get("timeframe"))
    use_fill = args.fill_missing or bool(data_cfg.get("fill_missing", True))
    if use_fill:
        tf_seconds = (
            parse_timeframe(tf).seconds if tf is not None else frame.timeframe_seconds_inferred()
        )
        frame, _ = fill_missing_intervals(frame, tf_seconds)

    shadow_cfg_obj = cfg.get("shadow", {})
    shadow_cfg: dict[str, Any] = (
        cast(dict[str, Any], shadow_cfg_obj) if isinstance(shadow_cfg_obj, dict) else {}
    )
    runner_cfg = ShadowRunnerConfig(
        symbol=cast(str, shadow_cfg.get("symbol", "BTC-PERP")),
        target_directional_vol=float(shadow_cfg.get("target_directional_vol", 0.20)),
        min_realized_vol=float(shadow_cfg.get("min_realized_vol", 1e-6)),
        vol_spike_threshold=float(shadow_cfg.get("vol_spike_threshold", 0.90)),
    )

    logs = run_shadow(frame, config=runner_cfg)
    with args.output.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "regime",
                "intended_order",
                "hypothetical_fill",
                "slippage_estimate_bps",
                "skipped",
                "reason",
                "route_hint",
            ],
        )
        w.writeheader()
        w.writerows(logs)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
