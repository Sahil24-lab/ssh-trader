#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

from ssh_trader.data.clean import fill_missing_intervals, normalize_and_sort
from ssh_trader.data.gaps import count_missing_intervals
from ssh_trader.data.hyperliquid_history import (
    HistoryRow,
    fetch_candles,
    fetch_funding_history,
    fetch_latest_open_interest,
    merge_history_rows,
    parse_time_ms,
    ts_ms_to_utc_iso,
)
from ssh_trader.data.model import OHLCVFrame, parse_timeframe
from ssh_trader.data.resample import resample_ohlcv


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch Hyperliquid 1H candles and emit deterministic 4H resample."
    )
    p.add_argument("--coin", required=True, help="Coin symbol, e.g. BTC")
    p.add_argument("--start", required=True, help="Start time (ms epoch or ISO8601)")
    p.add_argument("--end", required=True, help="End time (ms epoch or ISO8601)")
    p.add_argument(
        "--base-url",
        default="https://api.hyperliquid.xyz",
        help="Hyperliquid API base URL",
    )
    p.add_argument(
        "--open-interest",
        choices=["none", "latest_ctx"],
        default="latest_ctx",
        help="Open interest mode",
    )
    p.add_argument("--timeout-s", type=float, default=15.0)
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Output directory for CSVs (default: data/).",
    )
    p.add_argument(
        "--fill-missing",
        action="store_true",
        help="Fill missing 1H intervals deterministically before resampling.",
    )
    p.add_argument(
        "--no-emit-4h",
        action="store_true",
        help="Do not emit 4H resample output.",
    )
    return p


def _frame_from_rows(rows: list[HistoryRow]) -> OHLCVFrame:
    ts: list[datetime] = []
    open_: list[float] = []
    high: list[float] = []
    low: list[float] = []
    close: list[float] = []
    volume: list[float] = []
    funding: list[float] = []
    oi: list[float] = []

    for row in rows:
        ts_ms = row.ts_ms
        ts.append(datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc))
        open_.append(row.open)
        high.append(row.high)
        low.append(row.low)
        close.append(row.close)
        volume.append(row.volume)
        funding.append(row.funding)
        oi.append(row.open_interest)

    return OHLCVFrame(
        ts=ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        funding=funding,
        open_interest=oi,
    )


def _write_csv(path: Path, frame: OHLCVFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["timestamp", "open", "high", "low", "close", "volume", "funding", "open_interest"]
        )
        for i in range(len(frame)):
            w.writerow(
                [
                    frame.ts[i].isoformat().replace("+00:00", "Z"),
                    frame.open[i],
                    frame.high[i],
                    frame.low[i],
                    frame.close[i],
                    frame.volume[i],
                    (frame.funding[i] if frame.funding is not None else 0.0),
                    (frame.open_interest[i] if frame.open_interest is not None else 0.0),
                ]
            )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    start_ms = parse_time_ms(args.start)
    end_ms = parse_time_ms(args.end)
    if end_ms <= start_ms:
        raise ValueError("end must be after start")

    tf_1h = parse_timeframe("1h").seconds
    tf_4h = parse_timeframe("4h").seconds

    candles = fetch_candles(
        base_url=args.base_url,
        coin=args.coin,
        interval="1h",
        start_ms=start_ms,
        end_ms=end_ms,
        timeout_s=args.timeout_s,
    )
    if not candles:
        raise SystemExit(
            "no candles returned. Likely causes: (1) your start/end is outside the most recent "
            "~5000 candles for 1h, or (2) candleSnapshot request parameters are invalid."
        )

    funding = fetch_funding_history(
        base_url=args.base_url,
        coin=args.coin,
        start_ms=start_ms,
        end_ms=end_ms,
        timeout_s=args.timeout_s,
    )
    open_interest = 0.0
    if args.open_interest == "latest_ctx":
        open_interest = fetch_latest_open_interest(
            base_url=args.base_url,
            coin=args.coin,
            timeout_s=args.timeout_s,
        )
    rows = merge_history_rows(
        candles=candles,
        funding=funding,
        default_open_interest=open_interest,
    )

    frame = _frame_from_rows(rows)
    frame, stats = normalize_and_sort(frame)

    missing_before = count_missing_intervals(frame.ts, tf_1h)
    filled = 0
    if args.fill_missing:
        frame, fill_stats = fill_missing_intervals(frame, tf_1h)
        filled = fill_stats.filled

    missing_after = count_missing_intervals(frame.ts, tf_1h)

    coin_lower = args.coin.strip().lower()
    out_1h = args.output_dir / f"hyperliquid_{coin_lower}_1h.csv"
    _write_csv(out_1h, frame)

    print(f"[1h] wrote {len(frame)} rows to {out_1h}")
    if len(frame) > 0:
        print(f"[1h] start={frame.ts[0].isoformat().replace('+00:00','Z')}")
        print(f"[1h] end  ={frame.ts[-1].isoformat().replace('+00:00','Z')}")
    print(f"[1h] sorted={stats.sorted} deduped={stats.deduped}")
    print(
        f"[1h] missing_before_fill={missing_before} filled={filled} "
        f"missing_after_fill={missing_after}"
    )
    print(
        f"[1h] requested_start={ts_ms_to_utc_iso(start_ms)} "
        f"requested_end={ts_ms_to_utc_iso(end_ms)}"
    )

    if not args.no_emit_4h:
        frame_4h = resample_ohlcv(frame, tf_4h)
        out_4h = args.output_dir / f"hyperliquid_{coin_lower}_4h.csv"
        _write_csv(out_4h, frame_4h)
        print(f"[4h] wrote {len(frame_4h)} rows to {out_4h}")
        if len(frame_4h) > 0:
            print(f"[4h] start={frame_4h.ts[0].isoformat().replace('+00:00','Z')}")
            print(f"[4h] end  ={frame_4h.ts[-1].isoformat().replace('+00:00','Z')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
