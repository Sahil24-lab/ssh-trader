from ssh_trader.guidance.policy import GuidancePolicy, GuidancePolicyConfig
from ssh_trader.nav.regime import Regime


def test_guidance_policy_targets_within_bands() -> None:
    policy = GuidancePolicy(GuidancePolicyConfig(aggressiveness=0.5))

    off = policy.targets(Regime.RISK_OFF)
    assert 0.80 <= off.carry_frac <= 1.00
    assert 0.00 <= off.directional_frac <= 0.10

    neutral = policy.targets(Regime.NEUTRAL)
    assert 0.60 <= neutral.carry_frac <= 0.80
    assert 0.10 <= neutral.directional_frac <= 0.30

    on = policy.targets(Regime.RISK_ON)
    assert 0.40 <= on.carry_frac <= 0.70
    assert 0.30 <= on.directional_frac <= 0.60
