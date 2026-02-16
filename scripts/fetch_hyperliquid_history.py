#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ssh_trader.data.hyperliquid_history import (
    fetch_candles,
    fetch_funding_history,
    fetch_latest_open_interest,
    merge_history_rows,
    parse_time_ms,
    ts_ms_to_utc_iso,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch Hyperliquid candles + funding into normalized CSV."
    )
    p.add_argument("--coin", required=True, help="Coin symbol, e.g. BTC")
    p.add_argument("--interval", default="1h", help="Candle interval, e.g. 1h")
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
    p.add_argument("--output", type=Path, required=True, help="Output CSV path")
    p.add_argument(
        "--debug",
        action="store_true",
        help="Print parsed times and basic fetch stats for troubleshooting",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    start_ms = parse_time_ms(args.start)
    end_ms = parse_time_ms(args.end)
    if end_ms <= start_ms:
        raise ValueError("end must be after start")

    if args.debug:
        print(f"[debug] start_ms={start_ms} ({ts_ms_to_utc_iso(start_ms)})")
        print(f"[debug] end_ms  ={end_ms} ({ts_ms_to_utc_iso(end_ms)})")
        print(f"[debug] coin={args.coin} interval={args.interval} base_url={args.base_url}")

    candles = fetch_candles(
        base_url=args.base_url,
        coin=args.coin,
        interval=args.interval,
        start_ms=start_ms,
        end_ms=end_ms,
        timeout_s=args.timeout_s,
    )
    if args.debug:
        print(f"[debug] candles_count={len(candles) if candles else 0}")
        if candles:
            # Try to show the first/last candle time if the fetcher returns dict-like rows
            first = candles[0]
            last = candles[-1]
            for label, c in (("first", first), ("last", last)):
                t = c.get("t") if hasattr(c, "get") else None
                if isinstance(t, int):
                    print(f"[debug] {label}_candle_t={t} ({ts_ms_to_utc_iso(t)})")

    if not candles:
        raise SystemExit(
            "no candles returned. Likely causes: (1) your start/end is outside the most recent "
            "~5000 candles for this interval, or (2) fetch_candles() is not using POST /info with "
            "type=candleSnapshot and req={coin,interval,startTime,endTime}."
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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["timestamp", "open", "high", "low", "close", "volume", "funding", "open_interest"]
        )
        for row in rows:
            writer.writerow(
                [
                    ts_ms_to_utc_iso(row.ts_ms),
                    row.open,
                    row.high,
                    row.low,
                    row.close,
                    row.volume,
                    row.funding,
                    row.open_interest,
                ]
            )

    print(f"wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
