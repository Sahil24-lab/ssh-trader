"""Replay CLI for regime labeling from OHLCV CSV.

This tool is intentionally limited to deterministic feature computation and labeling.
It does not place orders or simulate trading.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Literal, cast

from ssh_trader.data.clean import fill_missing_intervals, normalize_and_sort
from ssh_trader.data.io_csv import load_ohlcv_csv
from ssh_trader.data.model import parse_timeframe
from ssh_trader.data.resample import resample_ohlcv

from .compression import CompressionConfig, compression_score
from .features import trend_signal, volatility_features_from_close
from .regime import Regime, RegimeConfig, classify_regimes


def _load_config(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    with path.open("r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return cast(dict[str, object], data)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Replay regime labels from an OHLCV CSV.")
    p.add_argument("--csv", required=True, type=Path, help="Path to OHLCV CSV (header required).")
    p.add_argument("--config", type=Path, default=None, help="Optional JSON config file.")
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output CSV path (default stdout).",
    )

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
    p.add_argument("--no-fill-missing", action="store_true", help="Do not fill missing intervals.")
    p.add_argument(
        "--resample",
        type=str,
        default=None,
        help="Optional output timeframe (e.g. 4h).",
    )
    p.add_argument("--include-features", action="store_true", help="Output extra feature columns.")

    p.add_argument("--trend-method", choices=["sma", "ema"], default=None)
    p.add_argument("--long-ma-window", type=int, default=None)
    p.add_argument("--trend-span", type=int, default=None)
    p.add_argument("--trend-band", type=float, default=None)
    p.add_argument("--rv-window", type=int, default=None)
    p.add_argument("--vol-pct-window", type=int, default=None)
    p.add_argument("--annualization-factor", type=float, default=None)
    p.add_argument("--risk-on-vol-max", type=float, default=None)
    p.add_argument("--risk-off-vol-min", type=float, default=None)
    p.add_argument("--confirm-bars", type=int, default=None)

    p.add_argument("--funding-mode", choices=["ignore", "sign"], default="sign")
    p.add_argument(
        "--initial",
        choices=[r.value for r in Regime],
        default=Regime.NEUTRAL.value,
        help="Initial regime before enough history is available.",
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
    resample_tf = args.resample or (
        data_cfg.get("resample") if isinstance(data_cfg.get("resample"), str) else None
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

    if resample_tf is not None:
        frame = resample_ohlcv(frame, parse_timeframe(resample_tf).seconds)

    regime_cfg_obj = cfg.get("regime", {})
    regime_cfg: dict[str, Any] = (
        cast(dict[str, Any], regime_cfg_obj) if isinstance(regime_cfg_obj, dict) else {}
    )
    trend_method_raw = args.trend_method or regime_cfg.get("trend_method", "sma")
    if trend_method_raw not in ("sma", "ema"):
        raise ValueError("trend_method must be 'sma' or 'ema'")
    trend_method = cast(Literal["sma", "ema"], trend_method_raw)

    config = RegimeConfig(
        trend_method=trend_method,
        long_ma_window=int(args.long_ma_window or regime_cfg.get("long_ma_window", 200)),
        trend_span=int(args.trend_span or regime_cfg.get("trend_span", 200)),
        trend_band=float(
            args.trend_band if args.trend_band is not None else regime_cfg.get("trend_band", 0.0)
        ),
        rv_window=int(args.rv_window or regime_cfg.get("rv_window", 20)),
        vol_percentile_window=int(
            args.vol_pct_window or regime_cfg.get("vol_percentile_window", 252)
        ),
        annualization_factor=float(
            args.annualization_factor
            if args.annualization_factor is not None
            else regime_cfg.get("annualization_factor", 1.0)
        ),
        risk_on_vol_pct_max=float(
            args.risk_on_vol_max
            if args.risk_on_vol_max is not None
            else regime_cfg.get("risk_on_vol_pct_max", 0.7)
        ),
        risk_off_vol_pct_min=float(
            args.risk_off_vol_min
            if args.risk_off_vol_min is not None
            else regime_cfg.get("risk_off_vol_pct_min", 0.9)
        ),
        confirm_bars=int(args.confirm_bars or regime_cfg.get("confirm_bars", 3)),
        funding_mode=args.funding_mode,
    )

    regimes = classify_regimes(
        close=frame.close,
        high=frame.high,
        low=frame.low,
        funding=frame.funding if args.funding_mode != "ignore" else None,
        config=config,
        initial=Regime(args.initial),
    )

    if args.include_features:
        trend = trend_signal(
            close=frame.close,
            method=config.trend_method,
            window_or_span=(
                config.long_ma_window if config.trend_method == "sma" else config.trend_span
            ),
            band=config.trend_band,
        )
        vol_feats = volatility_features_from_close(
            close=frame.close,
            rv_window=config.rv_window,
            vol_percentile_window=config.vol_percentile_window,
            annualization_factor=config.annualization_factor,
            demean=False,
        )
        comp_cfg = CompressionConfig()
        score, width = compression_score(
            high=frame.high, low=frame.low, close=frame.close, config=comp_cfg
        )
    else:
        trend = []
        vol_feats = None
        score = []
        width = []

    out_f = args.output.open("w", newline="") if args.output is not None else sys.stdout
    try:
        writer = csv.writer(out_f)
        if args.include_features:
            writer.writerow(
                [
                    "timestamp",
                    "close",
                    "trend",
                    "vol_pct",
                    "compression_score",
                    "compression_width",
                    "regime",
                ]
            )
        else:
            writer.writerow(["timestamp", "regime"])

        for i, r in enumerate(regimes):
            t = frame.ts[i].isoformat().replace("+00:00", "Z")
            if not args.include_features:
                writer.writerow([t, r.value])
                continue

            vol_pct = vol_feats.vol_percentile[i] if vol_feats is not None else None
            writer.writerow(
                [
                    t,
                    frame.close[i],
                    trend[i],
                    "" if vol_pct is None else vol_pct,
                    "" if score[i] is None else score[i],
                    "" if width[i] is None else width[i],
                    r.value,
                ]
            )
    finally:
        if args.output is not None:
            out_f.close()

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
