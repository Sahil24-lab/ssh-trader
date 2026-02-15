import math

from ssh_trader.nav.indicators import (
    atr,
    drawdown,
    ema,
    log_returns,
    realized_volatility,
    sma,
    volatility_percentile,
)

_ABS_TOL = 1e-10


def _assert_close(actual: float, expected: float, *, abs_tol: float = _ABS_TOL) -> None:
    assert math.isfinite(actual)
    assert math.isfinite(expected)
    assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=abs_tol), (actual, expected)


def test_log_returns() -> None:
    prices = [1.0, math.e, math.e**2]
    out = log_returns(prices)
    assert len(out) == 2
    _assert_close(out[0], 1.0)
    _assert_close(out[1], 1.0)


def test_sma_window_2() -> None:
    out = sma([1.0, 2.0, 3.0, 4.0], window=2)
    assert out == [None, 1.5, 2.5, 3.5]


def test_ema_span_2() -> None:
    out = ema([1.0, 2.0, 3.0], span=2)
    assert len(out) == 3
    _assert_close(out[0], 1.0)
    _assert_close(out[1], 1.6666666666666665)
    _assert_close(out[2], 2.5555555555555554)


def test_atr_wilder_window_3() -> None:
    high = [10.0, 11.0, 12.0, 11.0]
    low = [9.0, 9.5, 10.0, 9.0]
    close = [9.5, 10.5, 11.0, 10.0]
    out = atr(high, low, close, window=3, smoothing="wilder")
    assert out[:2] == [None, None]
    assert out[2] is not None
    assert out[3] is not None
    _assert_close(out[2], 1.5)
    _assert_close(out[3], 5.0 / 3.0)


def test_realized_volatility_rolling() -> None:
    rets = [0.0, 0.1, -0.1, 0.2]
    out = realized_volatility(rets, window=3)
    assert out[:2] == [None, None]
    assert out[2] is not None
    assert out[3] is not None
    _assert_close(out[2], math.sqrt((0.0**2 + 0.1**2 + (-0.1) ** 2) / 3.0))
    _assert_close(out[3], math.sqrt((0.1**2 + (-0.1) ** 2 + 0.2**2) / 3.0))


def test_volatility_percentile_window_3() -> None:
    vols = [1.0, 3.0, 2.0, 4.0]
    out = volatility_percentile(vols, window=3)
    assert out[:2] == [None, None]
    assert out[2] is not None
    assert out[3] is not None
    _assert_close(out[2], 2.0 / 3.0)
    _assert_close(out[3], 1.0)


def test_drawdown_series() -> None:
    values = [100.0, 110.0, 105.0, 120.0, 90.0]
    out = drawdown(values)
    assert out[0] == 0.0
    assert out[1] == 0.0
    _assert_close(out[2], 105.0 / 110.0 - 1.0)
    assert out[3] == 0.0
    _assert_close(out[4], 90.0 / 120.0 - 1.0)
