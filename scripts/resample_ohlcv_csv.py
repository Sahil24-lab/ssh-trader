#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ssh_trader.data.clean import fill_missing_intervals, normalize_and_sort
from ssh_trader.data.io_csv import load_ohlcv_csv
from ssh_trader.data.model import OHLCVFrame, parse_timeframe
from ssh_trader.data.resample import resample_ohlcv


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Resample an OHLCV CSV deterministically.")
    p.add_argument("--csv", type=Path, required=True, help="Input OHLCV CSV path.")
    p.add_argument("--timeframe", type=str, required=True, help="Input timeframe (e.g. 1h).")
    p.add_argument("--out-timeframe", type=str, required=True, help="Output timeframe (e.g. 4h).")
    p.add_argument(
        "--fill-missing",
        action="store_true",
        help="Fill missing intervals deterministically before resampling.",
    )
    p.add_argument("--output", type=Path, required=True, help="Output resampled CSV.")
    return p


def _write_csv(path: Path, frame: OHLCVFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "funding",
                "open_interest",
            ]
        )
        for i in range(len(frame.ts)):
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
    frame = load_ohlcv_csv(args.csv)
    frame, _ = normalize_and_sort(frame)

    tf_seconds = parse_timeframe(args.timeframe).seconds
    if args.fill_missing:
        frame, _ = fill_missing_intervals(frame, tf_seconds)

    out_tf_seconds = parse_timeframe(args.out_timeframe).seconds
    out = resample_ohlcv(frame, out_tf_seconds)
    _write_csv(args.output, out)
    print(f"wrote {len(out)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
