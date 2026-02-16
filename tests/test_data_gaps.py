from datetime import datetime, timedelta, timezone

import pytest

from ssh_trader.data.gaps import count_missing_intervals


def test_count_missing_intervals_counts_missing_bars() -> None:
    ts0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
    ts = [ts0, ts0 + timedelta(hours=1), ts0 + timedelta(hours=3)]
    assert count_missing_intervals(ts, timeframe_seconds=3600) == 1


def test_count_missing_intervals_raises_on_non_increasing() -> None:
    ts0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
    ts = [ts0, ts0]
    with pytest.raises(ValueError, match="strictly increasing"):
        count_missing_intervals(ts, timeframe_seconds=3600)
