from __future__ import annotations

import math
from dataclasses import dataclass

from ssh_trader.nav.regime import Regime


@dataclass(frozen=True, slots=True)
class AllocationBand:
    """Inclusive allocation band expressed as fraction of NAV."""

    min_frac: float
    max_frac: float

    def __post_init__(self) -> None:
        for name, value in (("min_frac", self.min_frac), ("max_frac", self.max_frac)):
            if not math.isfinite(value) or value < 0.0 or value > 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        if self.min_frac > self.max_frac:
            raise ValueError("min_frac must be <= max_frac")

    def pick(self, *, aggressiveness: float) -> float:
        """Pick a point in-band: 0 -> min, 1 -> max."""
        if not math.isfinite(aggressiveness) or aggressiveness < 0.0 or aggressiveness > 1.0:
            raise ValueError("aggressiveness must be finite and in [0, 1]")
        return self.min_frac + aggressiveness * (self.max_frac - self.min_frac)


@dataclass(frozen=True, slots=True)
class GuidancePolicyConfig:
    """Regime -> (carry %, directional %) bands."""

    risk_off_carry: AllocationBand = AllocationBand(0.80, 1.00)
    risk_off_directional: AllocationBand = AllocationBand(0.00, 0.10)

    neutral_carry: AllocationBand = AllocationBand(0.60, 0.80)
    neutral_directional: AllocationBand = AllocationBand(0.10, 0.30)

    risk_on_carry: AllocationBand = AllocationBand(0.40, 0.70)
    risk_on_directional: AllocationBand = AllocationBand(0.30, 0.60)

    aggressiveness: float = 0.5

    def __post_init__(self) -> None:
        if not math.isfinite(self.aggressiveness) or not (0.0 <= self.aggressiveness <= 1.0):
            raise ValueError("aggressiveness must be finite and in [0, 1]")


@dataclass(frozen=True, slots=True)
class TargetAllocations:
    carry_frac: float
    directional_frac: float


class GuidancePolicy:
    """Deterministic guidance mapping from regime label to target allocations."""

    def __init__(self, config: GuidancePolicyConfig | None = None) -> None:
        self._config = config if config is not None else GuidancePolicyConfig()

    @property
    def config(self) -> GuidancePolicyConfig:
        return self._config

    def targets(self, regime: Regime) -> TargetAllocations:
        cfg = self._config
        a = cfg.aggressiveness
        if regime == Regime.RISK_OFF:
            carry = cfg.risk_off_carry.pick(aggressiveness=a)
            directional = cfg.risk_off_directional.pick(aggressiveness=a)
        elif regime == Regime.RISK_ON:
            carry = cfg.risk_on_carry.pick(aggressiveness=a)
            directional = cfg.risk_on_directional.pick(aggressiveness=a)
        else:
            carry = cfg.neutral_carry.pick(aggressiveness=a)
            directional = cfg.neutral_directional.pick(aggressiveness=a)

        carry = max(0.0, min(1.0, carry))
        directional = max(0.0, min(1.0, directional))
        return TargetAllocations(carry_frac=carry, directional_frac=directional)
