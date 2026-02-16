from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Literal, cast

from ssh_trader.data.clean import fill_missing_intervals, normalize_and_sort
from ssh_trader.data.io_csv import load_ohlcv_csv
from ssh_trader.data.model import parse_timeframe
from ssh_trader.guidance.policy import GuidancePolicy, GuidancePolicyConfig
from ssh_trader.nav.compression import CompressionConfig
from ssh_trader.nav.regime import Regime, RegimeConfig
from ssh_trader.risk.governor import RiskConfig, RiskGovernor

from .metrics import compute_metrics
from .simulator import FeeModel, SimulatorConfig, SlippageModel, simulate_portfolio


def _load_config(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return cast(dict[str, object], data)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Portfolio simulator (no execution).")
    p.add_argument("--csv", required=True, type=Path, help="OHLCV CSV path.")
    p.add_argument("--config", type=Path, default=None, help="Optional JSON config.")
    p.add_argument(
        "--timeframe",
        type=str,
        default=None,
        help="Expected input timeframe (e.g. 1h).",
    )
    p.add_argument(
        "--fill-missing",
        action="store_true",
        help="Fill missing intervals deterministically.",
    )
    p.add_argument(
        "--no-fill-missing",
        action="store_true",
        help="Disable missing-interval filling.",
    )
    p.add_argument(
        "--output-metrics",
        type=Path,
        default=None,
        help="Optional metrics CSV output.",
    )
    p.add_argument(
        "--output-bars",
        type=Path,
        default=None,
        help="Optional per-bar CSV output for visualization.",
    )
    p.add_argument(
        "--output-trades",
        type=Path,
        default=None,
        help="Optional trade event CSV output for visualization.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = _load_config(args.config)

    data_cfg_obj = cfg.get("data", {})
    data_cfg: dict[str, Any] = (
        cast(dict[str, Any], data_cfg_obj) if isinstance(data_cfg_obj, dict) else {}
    )

    timeframe = args.timeframe or (
        data_cfg.get("timeframe") if isinstance(data_cfg.get("timeframe"), str) else None
    )

    if args.no_fill_missing:
        fill_missing = False
    elif args.fill_missing:
        fill_missing = True
    else:
        fill_missing = bool(data_cfg.get("fill_missing", True))

    frame = load_ohlcv_csv(args.csv)
    frame, _ = normalize_and_sort(frame)

    if fill_missing:
        tf_seconds = (
            parse_timeframe(timeframe).seconds
            if timeframe is not None
            else frame.timeframe_seconds_inferred()
        )
        frame, _ = fill_missing_intervals(frame, tf_seconds)

    guidance_cfg_obj = cfg.get("guidance", {})
    guidance_cfg: dict[str, Any] = (
        cast(dict[str, Any], guidance_cfg_obj) if isinstance(guidance_cfg_obj, dict) else {}
    )
    guidance = GuidancePolicy(
        GuidancePolicyConfig(aggressiveness=float(guidance_cfg.get("aggressiveness", 0.5)))
    )

    risk_cfg_obj = cfg.get("risk", {})
    risk_cfg: dict[str, Any] = (
        cast(dict[str, Any], risk_cfg_obj) if isinstance(risk_cfg_obj, dict) else {}
    )

    kill_action_raw_obj = risk_cfg.get("kill_switch_action", "carry_only")
    if not isinstance(kill_action_raw_obj, str):
        raise ValueError("kill_switch_action must be a string")
    if kill_action_raw_obj not in ("carry_only", "flat"):
        raise ValueError("kill_switch_action must be 'carry_only' or 'flat'")
    kill_action: Literal["carry_only", "flat"] = cast(
        Literal["carry_only", "flat"], kill_action_raw_obj
    )

    risk = RiskGovernor(
        RiskConfig(
            leverage_cap=float(risk_cfg.get("leverage_cap", 1.5)),
            venue_cap_frac=float(risk_cfg.get("venue_cap_frac", 0.30)),
            max_drawdown=float(risk_cfg.get("max_drawdown", 0.20)),
            kill_switch_action=kill_action,
            vol_spike_vol_pct=float(risk_cfg.get("vol_spike_vol_pct", 0.90)),
        )
    )

    nav_cfg_obj = cfg.get("nav", {})
    nav_cfg: dict[str, Any] = (
        cast(dict[str, Any], nav_cfg_obj) if isinstance(nav_cfg_obj, dict) else {}
    )
    nav_config = RegimeConfig(
        long_ma_window=int(nav_cfg.get("long_ma_window", 200)),
        rv_window=int(nav_cfg.get("rv_window", 20)),
        vol_percentile_window=int(nav_cfg.get("vol_percentile_window", 252)),
        confirm_bars=int(nav_cfg.get("confirm_bars", 3)),
    )

    comp_cfg_obj = cfg.get("compression", {})
    comp_cfg: dict[str, Any] = (
        cast(dict[str, Any], comp_cfg_obj) if isinstance(comp_cfg_obj, dict) else {}
    )
    compression_config = CompressionConfig(
        atr_window=int(comp_cfg.get("atr_window", 14)),
        contraction_lookback=int(comp_cfg.get("contraction_lookback", 50)),
        vol_pct_window=int(comp_cfg.get("vol_pct_window", 252)),
        range_window=int(comp_cfg.get("range_window", 50)),
    )

    sim_cfg_obj = cfg.get("sim", {})
    sim_cfg: dict[str, Any] = (
        cast(dict[str, Any], sim_cfg_obj) if isinstance(sim_cfg_obj, dict) else {}
    )
    sim_config = SimulatorConfig(
        initial_nav=float(sim_cfg.get("initial_nav", 1_000_000.0)),
        carry_funding_freq_hours=int(sim_cfg.get("carry_funding_freq_hours", 8)),
        liquidation_buffer=float(sim_cfg.get("liquidation_buffer", 0.10)),
        target_dir_vol=float(sim_cfg.get("target_dir_vol", 0.20)),
    )

    fees_obj = cfg.get("fees", {})
    fees: dict[str, Any] = cast(dict[str, Any], fees_obj) if isinstance(fees_obj, dict) else {}
    fee_model = FeeModel(taker_fee_bps=float(fees.get("taker_fee_bps", 5.0)))
    slippage_model = SlippageModel(
        slippage_bps_at_1x_nav=float(fees.get("slippage_bps_at_1x_nav", 10.0))
    )

    result = simulate_portfolio(
        frame=frame,
        guidance=guidance,
        risk=risk,
        fee_model=fee_model,
        slippage_model=slippage_model,
        nav_config=nav_config,
        compression_config=compression_config,
        sim_config=sim_config,
    )
    metrics = compute_metrics(result)

    rows = [
        ["cagr", metrics.cagr],
        ["sharpe", metrics.sharpe],
        ["sortino", metrics.sortino],
        ["max_drawdown", metrics.max_drawdown],
        ["win_rate", metrics.win_rate],
        ["exposure_utilization", metrics.exposure_utilization],
        ["funding_contribution", metrics.funding_contribution],
        ["directional_contribution", metrics.directional_contribution],
        ["return_risk_off", metrics.regime_returns.get(Regime.RISK_OFF, 0.0)],
        ["return_neutral", metrics.regime_returns.get(Regime.NEUTRAL, 0.0)],
        ["return_risk_on", metrics.regime_returns.get(Regime.RISK_ON, 0.0)],
    ]

    if args.output_metrics is None:
        for k, v in rows:
            print(f"{k},{v}")
    else:
        with args.output_metrics.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            w.writerows(rows)

    if args.output_bars is not None:
        args.output_bars.parent.mkdir(parents=True, exist_ok=True)
        with args.output_bars.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "timestamp",
                    "nav",
                    "regime",
                    "carry_notional",
                    "directional_notional",
                    "gross_exposure",
                    "leverage",
                    "pnl_price",
                    "pnl_funding",
                    "pnl_fees",
                    "pnl_slippage",
                    "kill_switch_active",
                ]
            )
            for bar in result.bars:
                w.writerow(
                    [
                        bar.ts.isoformat().replace("+00:00", "Z"),
                        bar.nav,
                        bar.regime.value,
                        bar.carry_notional,
                        bar.directional_notional,
                        bar.gross_exposure,
                        bar.leverage,
                        bar.pnl_price,
                        bar.pnl_funding,
                        bar.pnl_fees,
                        bar.pnl_slippage,
                        int(bar.kill_switch_active),
                    ]
                )

    if args.output_trades is not None:
        args.output_trades.parent.mkdir(parents=True, exist_ok=True)
        with args.output_trades.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts", "leg", "qty_delta", "price", "notional", "fee", "slippage"])
            for t in result.trades:
                w.writerow(
                    [
                        t.ts.isoformat().replace("+00:00", "Z"),
                        t.leg,
                        t.qty_delta,
                        t.price,
                        t.notional,
                        t.fee,
                        t.slippage,
                    ]
                )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
