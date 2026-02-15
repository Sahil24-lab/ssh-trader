"""Placeholder implementation for the nav subsystem."""

from dataclasses import dataclass


@dataclass(slots=True)
class NavComponent:
    """Minimal placeholder component for the nav subsystem."""

    name: str = "nav"

    def describe(self) -> str:
        """Return a human-readable subsystem description."""
        return f"{self.name}: placeholder subsystem"
