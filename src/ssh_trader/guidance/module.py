"""Placeholder implementation for the guidance subsystem."""

from dataclasses import dataclass


@dataclass(slots=True)
class GuidanceComponent:
    """Minimal placeholder component for the guidance subsystem."""

    name: str = "guidance"

    def describe(self) -> str:
        """Return a human-readable subsystem description."""
        return f"{self.name}: placeholder subsystem"
