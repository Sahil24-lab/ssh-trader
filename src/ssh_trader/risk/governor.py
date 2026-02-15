from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class RiskConfig:
    leverage_cap: float = 1.5
    venue_cap_frac: float = 0.30
    max_drawdown: float = 0.20
    kill_switch_action: Literal["carry_only", "flat"] = "carry_only"
    vol_spike_vol_pct: float = 0.90

    def __post_init__(self) -> None:
        if not math.isfinite(self.leverage_cap) or self.leverage_cap <= 0.0:
            raise ValueError("leverage_cap must be finite and positive")
        if not math.isfinite(self.venue_cap_frac) or not (0.0 < self.venue_cap_frac <= 1.0):
            raise ValueError("venue_cap_frac must be finite and in (0, 1]")
        if not math.isfinite(self.max_drawdown) or not (0.0 < self.max_drawdown < 1.0):
            raise ValueError("max_drawdown must be finite and in (0, 1)")
        if self.kill_switch_action not in ("carry_only", "flat"):
            raise ValueError("kill_switch_action must be 'carry_only' or 'flat'")
        if not math.isfinite(self.vol_spike_vol_pct) or not (0.0 < self.vol_spike_vol_pct <= 1.0):
            raise ValueError("vol_spike_vol_pct must be finite and in (0, 1]")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    kill_switch_active: bool
    mode: Literal["normal", "carry_only", "flat"]
    venue_cap_applied: float
    leverage_cap_applied: float
    directional_allowed: bool


class RiskGovernor:
    def __init__(self, config: RiskConfig | None = None) -> None:
        self._config = config if config is not None else RiskConfig()

    @property
    def config(self) -> RiskConfig:
        return self._config

    def decide(
        self,
        *,
        nav: float,
        peak_nav: float,
        vol_pct: float | None,
        requested_directional: bool,
    ) -> RiskDecision:
        cfg = self._config
        if nav <= 0.0 or not math.isfinite(nav):
            raise ValueError("nav must be finite and positive")
        if peak_nav <= 0.0 or not math.isfinite(peak_nav):
            raise ValueError("peak_nav must be finite and positive")

        dd = 1.0 - (nav / peak_nav)
        kill = dd >= (cfg.max_drawdown - 1e-12)
        if kill:
            mode: Literal["normal", "carry_only", "flat"] = (
                "flat" if cfg.kill_switch_action == "flat" else "carry_only"
            )
        else:
            mode = "normal"

        directional_allowed = requested_directional and mode == "normal"
        if vol_pct is not None and vol_pct >= cfg.vol_spike_vol_pct:
            directional_allowed = False

        return RiskDecision(
            kill_switch_active=kill,
            mode=mode,
            venue_cap_applied=cfg.venue_cap_frac,
            leverage_cap_applied=cfg.leverage_cap,
            directional_allowed=directional_allowed,
        )
