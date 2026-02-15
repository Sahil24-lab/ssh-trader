from ssh_trader.nav.compression import CompressionConfig, compression_score, expansion_trigger
from ssh_trader.nav.features import trend_signal, volatility_features_from_close


def test_compression_score_higher_in_tight_range() -> None:
    # First half: wide range; second half: tight range.
    close = [100.0 + i * 0.1 for i in range(20)]
    high = [c + (2.0 if i < 10 else 0.2) for i, c in enumerate(close)]
    low = [c - (2.0 if i < 10 else 0.2) for i, c in enumerate(close)]

    cfg = CompressionConfig(atr_window=3, contraction_lookback=5, vol_pct_window=5, range_window=5)
    score, width = compression_score(high=high, low=low, close=close, config=cfg)
    assert len(score) == len(close)
    assert len(width) == len(close)

    # Compare average score in each region after warmup.
    left = [s for s in score[8:10] if s is not None]
    right = [s for s in score[18:20] if s is not None]
    assert left and right
    assert sum(right) / len(right) > sum(left) / len(left)


def test_expansion_trigger_after_compression_breakout() -> None:
    close = [100.0 + i * 0.2 for i in range(10)] + [102.0] * 10 + [105.0, 108.0]
    high = [c + (2.0 if i < 10 else (0.2 if i < 20 else 1.0)) for i, c in enumerate(close)]
    low = [c - (2.0 if i < 10 else (0.2 if i < 20 else 1.0)) for i, c in enumerate(close)]

    cfg = CompressionConfig(
        atr_window=3,
        contraction_lookback=10,
        vol_pct_window=5,
        range_window=10,
        breakout_confirm=2,
        score_trigger=0.05,
        vol_expand_threshold=0.2,
        vol_pct_low_threshold=0.8,
    )

    score, _ = compression_score(high=high, low=low, close=close, config=cfg)
    vol_feats = volatility_features_from_close(close=close, rv_window=3, vol_percentile_window=5)
    trend = trend_signal(close=close, method="sma", window_or_span=3, band=0.0)

    trig = expansion_trigger(
        close=close,
        high=high,
        low=low,
        vol_pct=vol_feats.vol_percentile,
        trend=trend,
        score=score,
        config=cfg,
    )
    assert len(trig) == len(close)
    assert any(trig[-3:])  # trigger near the breakout
