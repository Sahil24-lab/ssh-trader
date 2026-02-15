from ssh_trader.nav.regime import Regime, RegimeConfig, classify_regimes, next_regime


def test_next_regime_risk_on_entry() -> None:
    cfg = RegimeConfig(risk_on_vol_pct_max=0.6, risk_off_vol_pct_min=0.9)
    out = next_regime(previous=Regime.NEUTRAL, trend=1, vol_pct=0.5, config=cfg, funding_sign=0)
    assert out == Regime.RISK_ON


def test_next_regime_funding_sign_downgrades_risk_on() -> None:
    cfg = RegimeConfig(risk_on_vol_pct_max=0.6, risk_off_vol_pct_min=0.9, funding_mode="sign")
    out = next_regime(previous=Regime.NEUTRAL, trend=1, vol_pct=0.5, config=cfg, funding_sign=1)
    assert out == Regime.NEUTRAL


def test_next_regime_risk_on_hysteresis_exit() -> None:
    cfg = RegimeConfig(risk_on_vol_pct_max=0.6, risk_on_exit_vol_pct=0.8, risk_off_vol_pct_min=0.9)
    stay = next_regime(previous=Regime.RISK_ON, trend=1, vol_pct=0.75, config=cfg, funding_sign=0)
    exit_ = next_regime(previous=Regime.RISK_ON, trend=1, vol_pct=0.85, config=cfg, funding_sign=0)
    assert stay == Regime.RISK_ON
    assert exit_ == Regime.NEUTRAL


def test_next_regime_risk_off_trigger_and_exit() -> None:
    cfg = RegimeConfig(risk_off_vol_pct_min=0.9, risk_off_exit_vol_pct=0.8)
    triggered = next_regime(
        previous=Regime.NEUTRAL,
        trend=1,
        vol_pct=0.95,
        config=cfg,
        funding_sign=0,
    )
    stay = next_regime(previous=Regime.RISK_OFF, trend=1, vol_pct=0.85, config=cfg, funding_sign=0)
    exit_ = next_regime(previous=Regime.RISK_OFF, trend=1, vol_pct=0.75, config=cfg, funding_sign=0)
    assert triggered == Regime.RISK_OFF
    assert stay == Regime.RISK_OFF
    assert exit_ == Regime.NEUTRAL


def test_classify_regimes_basic_uptrend() -> None:
    close = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    cfg = RegimeConfig(
        trend_method="sma",
        long_ma_window=2,
        rv_window=2,
        vol_percentile_window=2,
        risk_on_vol_pct_max=1.0,
        risk_off_vol_pct_min=1.0,
        risk_on_exit_vol_pct=1.0,
        confirm_bars=1,
        funding_mode="ignore",
    )
    regimes = classify_regimes(close=close, config=cfg, initial=Regime.NEUTRAL)
    assert len(regimes) == len(close)
    assert regimes[:3] == [Regime.NEUTRAL, Regime.NEUTRAL, Regime.NEUTRAL]
    assert all(r == Regime.RISK_ON for r in regimes[3:])
