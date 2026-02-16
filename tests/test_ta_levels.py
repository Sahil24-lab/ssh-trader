from ssh_trader.ta.levels import (
    Level,
    LevelClusterConfig,
    LevelScoreConfig,
    PivotConfig,
    _score_levels,
    build_levels,
    compute_level_proximity,
    detect_pivots,
)


def test_detect_pivots_simple() -> None:
    high = [1, 3, 2, 4, 1]
    low = [1, 1, 0, 1, 1]
    piv_h, piv_l = detect_pivots(high, low, PivotConfig(k=1))
    assert piv_h == [False, True, False, True, False]
    assert piv_l == [False, False, True, False, False]


def test_build_levels_clustered_support_resistance() -> None:
    n = 30
    high = [100.0] * n
    low = [100.0] * n
    close = [100.0] * n
    for i in (5, 10, 15):
        high[i] = 110.0
    for i in (7, 12, 17):
        low[i] = 90.0
    atr_series = [2.0] * n
    levels = build_levels(
        high,
        low,
        close,
        atr_series=atr_series,
        pivot_config=PivotConfig(k=1),
        cluster_config=LevelClusterConfig(band_atr_mult=1.0, min_touches=3, reaction_atr_mult=0.0),
        score_config=LevelScoreConfig(top_n=3),
    )
    kinds = [lvl.kind for lvl in levels]
    assert "support" in kinds
    assert "resistance" in kinds
    centers = [round(lvl.center, 2) for lvl in levels]
    assert 90.0 in centers
    assert 110.0 in centers


def test_level_scoring_prefers_more_touches() -> None:
    lvl_a = Level(
        center=100.0,
        band_low=99.0,
        band_high=101.0,
        touch_count=3,
        touch_indices=[10, 20, 30],
        reaction_strength_atr=1.0,
        score=0.0,
        kind="support",
    )
    lvl_b = Level(
        center=102.0,
        band_low=101.0,
        band_high=103.0,
        touch_count=5,
        touch_indices=[5, 15, 25, 35, 45],
        reaction_strength_atr=1.0,
        score=0.0,
        kind="support",
    )
    scored = _score_levels([lvl_a, lvl_b], LevelScoreConfig(), last_idx=50)
    assert scored[1].score >= scored[0].score


def test_level_proximity_basic() -> None:
    levels = [
        Level(100.0, 99.0, 101.0, 3, [1, 2, 3], 1.2, 0.5, "support"),
        Level(110.0, 109.0, 111.0, 3, [1, 2, 3], 1.2, 0.6, "resistance"),
    ]
    close = [99.0, 105.0, 112.0]
    atr = [2.0, 2.0, 2.0]
    out = compute_level_proximity(close, atr, levels)
    assert out[0].level_kind == "support"
    assert out[1].level_kind == "support"
    assert out[2].level_kind == "resistance"
