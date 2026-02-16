from datetime import datetime, timedelta, timezone

from ssh_trader.data.model import OHLCVFrame
from ssh_trader.data.resample import resample_ohlcv


def test_resample_ohlcv_aggregates_and_aligns_to_epoch_buckets() -> None:
    ts0 = datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc)
    ts = [ts0 + timedelta(hours=i) for i in range(8)]
    open_ = [100.0 + i for i in range(8)]
    high = [o + 2.0 for o in open_]
    low = [o - 2.0 for o in open_]
    close = [o + 0.5 for o in open_]
    volume = [1.0] * 8
    funding = [0.0, 1.0, 2.0, 3.0, 10.0, 11.0, 12.0, 13.0]
    oi = [float(i) for i in range(8)]

    frame = OHLCVFrame(
        ts=ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        funding=funding,
        open_interest=oi,
    )
    out = resample_ohlcv(frame, out_timeframe_seconds=4 * 3600)

    assert len(out) == 3  # 01:00-03:00 in 00:00 bucket, then 04:00, then 08:00
    assert out.ts[0] == datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert out.ts[1] == datetime(2020, 1, 1, 4, 0, tzinfo=timezone.utc)
    assert out.ts[2] == datetime(2020, 1, 1, 8, 0, tzinfo=timezone.utc)

    # Bucket 00:00 includes hours 01,02,03
    assert out.open[0] == open_[0]
    assert out.close[0] == close[2]
    assert out.high[0] == max(high[0:3])
    assert out.low[0] == min(low[0:3])
    assert out.volume[0] == 3.0
    assert out.funding is not None and out.funding[0] == (0.0 + 1.0 + 2.0) / 3.0
    assert out.open_interest is not None and out.open_interest[0] == oi[2]
