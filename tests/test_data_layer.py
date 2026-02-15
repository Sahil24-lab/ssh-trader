import math
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from ssh_trader.data.clean import fill_missing_intervals, normalize_and_sort
from ssh_trader.data.io_csv import load_ohlcv_csv


def _write_csv(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_load_csv_timezone_normalization_and_sort() -> None:
    with TemporaryDirectory() as d:
        p = Path(d) / "ohlcv.csv"
        _write_csv(
            p,
            "timestamp,open,high,low,close,volume\n"
            "2020-01-01T00:00:00-05:00,1,1,1,1,10\n"
            "2020-01-01T04:00:00Z,2,2,2,2,20\n",
        )
        frame = load_ohlcv_csv(p)
        frame, _ = normalize_and_sort(frame)
        assert frame.ts[0].tzinfo is not None
        assert frame.ts[0].utcoffset() == timezone.utc.utcoffset(datetime.now(tz=timezone.utc))
        # First row is 2020-01-01 05:00 UTC; second is 04:00 UTC,
        # so after sort the 04:00 comes first.
        assert frame.close == [2.0, 1.0]


def test_fill_missing_intervals_inserts_synthetic_bars() -> None:
    with TemporaryDirectory() as d:
        p = Path(d) / "ohlcv.csv"
        _write_csv(
            p,
            "timestamp,open,high,low,close,volume,funding,open_interest\n"
            "2020-01-01T00:00:00Z,100,101,99,100,1,0.01,10\n"
            "2020-01-01T02:00:00Z,102,103,101,102,2,0.02,11\n",
        )
        frame = load_ohlcv_csv(p)
        frame, _ = normalize_and_sort(frame)
        filled, stats = fill_missing_intervals(frame, timeframe_seconds=3600)
        assert stats.filled == 1
        assert len(filled.ts) == 3
        # Synthetic middle bar carries forward the previous close with zero volume.
        assert filled.ts[1].isoformat().replace("+00:00", "Z") == "2020-01-01T01:00:00Z"
        assert filled.open[1] == 100.0
        assert filled.high[1] == 100.0
        assert filled.low[1] == 100.0
        assert filled.close[1] == 100.0
        assert filled.volume[1] == 0.0
        assert filled.funding is not None and math.isclose(filled.funding[1], 0.0)
        assert filled.open_interest is not None and math.isclose(filled.open_interest[1], 0.0)
