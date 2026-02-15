from ssh_trader.risk.governor import RiskConfig, RiskGovernor


def test_kill_switch_modes() -> None:
    carry_only = RiskGovernor(RiskConfig(max_drawdown=0.10, kill_switch_action="carry_only"))
    d = carry_only.decide(nav=90.0, peak_nav=100.0, vol_pct=None, requested_directional=True)
    assert d.kill_switch_active is True
    assert d.mode == "carry_only"
    assert d.directional_allowed is False

    flat = RiskGovernor(RiskConfig(max_drawdown=0.10, kill_switch_action="flat"))
    d = flat.decide(nav=90.0, peak_nav=100.0, vol_pct=None, requested_directional=True)
    assert d.kill_switch_active is True
    assert d.mode == "flat"
    assert d.directional_allowed is False


def test_vol_spike_derisk_disables_directional() -> None:
    gov = RiskGovernor(RiskConfig(vol_spike_vol_pct=0.8))
    d = gov.decide(nav=100.0, peak_nav=100.0, vol_pct=0.95, requested_directional=True)
    assert d.kill_switch_active is False
    assert d.directional_allowed is False
