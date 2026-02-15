"""Placeholder implementation for the live subsystem."""

from dataclasses import dataclass


@dataclass(slots=True)
class LiveComponent:
    """Minimal placeholder component for the live subsystem."""

    name: str = "live"

    def describe(self) -> str:
        """Return a human-readable subsystem description."""
        return f"{self.name}: placeholder subsystem"
