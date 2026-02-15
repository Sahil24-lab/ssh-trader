"""Placeholder implementation for the risk subsystem."""

from dataclasses import dataclass


@dataclass(slots=True)
class RiskComponent:
    """Minimal placeholder component for the risk subsystem."""

    name: str = "risk"

    def describe(self) -> str:
        """Return a human-readable subsystem description."""
        return f"{self.name}: placeholder subsystem"
