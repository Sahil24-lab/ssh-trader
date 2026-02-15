"""Placeholder implementation for the backtest subsystem."""

from dataclasses import dataclass


@dataclass(slots=True)
class BacktestComponent:
    """Minimal placeholder component for the backtest subsystem."""

    name: str = "backtest"

    def describe(self) -> str:
        """Return a human-readable subsystem description."""
        return f"{self.name}: placeholder subsystem"
