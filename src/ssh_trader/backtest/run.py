from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Literal, cast

from ssh_trader.config.runtime import (
    build_compression_config,
    build_fee_model,
    build_guidance_policy,
    build_nav_config,
    build_risk_governor,
    build_simulator_config,
    build_slippage_model,
    load_json_config,
)
from ssh_trader.data.clean import fill_missing_intervals, normalize_and_sort
from ssh_trader.data.io_csv import load_ohlcv_csv
from ssh_trader.data.model import parse_timeframe
from ssh_trader.nav.regime import Regime, RegimeConfig

from .metrics import compute_metrics
from .simulator import simulate_portfolio


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
        "--initial-nav",
        type=float,
        default=None,
        help="Override starting NAV (USD) (overrides config sim.initial_nav).",
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
    p.add_argument(
        "--output-lifecycle",
        type=Path,
        default=None,
        help="Optional trade lifecycle CSV output for visualization.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_json_config(args.config)

    data_cfg_obj = cfg.get("data", {})
    data_cfg: dict[str, object] = (
        cast(dict[str, object], data_cfg_obj) if isinstance(data_cfg_obj, dict) else {}
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

    guidance = build_guidance_policy(cfg)
    risk = build_risk_governor(cfg, default_kill_switch_action="carry_only")
    nav_config = build_nav_config(cfg)
    compression_config = build_compression_config(cfg)
    sim_config = build_simulator_config(cfg, initial_nav_override=args.initial_nav)
    fee_model = build_fee_model(cfg)
    slippage_model = build_slippage_model(cfg)

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
        ["initial_nav", sim_config.initial_nav],
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
                    "price",
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
                        bar.price,
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
            w.writerow(["ts", "leg", "source", "qty_delta", "price", "notional", "fee", "slippage"])
            for t in result.trades:
                w.writerow(
                    [
                        t.ts.isoformat().replace("+00:00", "Z"),
                        t.leg,
                        t.source,
                        t.qty_delta,
                        t.price,
                        t.notional,
                        t.fee,
                        t.slippage,
                    ]
                )

    if args.output_lifecycle is not None:
        args.output_lifecycle.parent.mkdir(parents=True, exist_ok=True)
        with args.output_lifecycle.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "open_ts",
                    "close_ts",
                    "kind",
                    "side",
                    "qty",
                    "entry_price",
                    "exit_price",
                    "nav_entry",
                    "nav_exit",
                    "nav_delta",
                    "nav_delta_pct",
                    "pnl_price",
                    "pnl_funding",
                    "pnl_fees",
                    "pnl_slippage",
                    "pnl_total",
                    "bars_held",
                    "exit_reason",
                ]
            )
            for lc in result.lifecycles:
                w.writerow(
                    [
                        lc.open_ts.isoformat().replace("+00:00", "Z"),
                        lc.close_ts.isoformat().replace("+00:00", "Z"),
                        lc.kind,
                        lc.side,
                        lc.qty,
                        lc.entry_price,
                        lc.exit_price,
                        lc.nav_entry,
                        lc.nav_exit,
                        lc.nav_delta,
                        "" if lc.nav_delta_pct is None else lc.nav_delta_pct,
                        lc.pnl_price,
                        lc.pnl_funding,
                        lc.pnl_fees,
                        lc.pnl_slippage,
                        lc.pnl_total,
                        lc.bars_held,
                        lc.exit_reason,
                    ]
                )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
