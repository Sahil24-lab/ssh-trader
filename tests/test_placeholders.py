"""Basic smoke tests for placeholder subsystem modules."""

from typing import Protocol

from ssh_trader.backtest import BacktestComponent
from ssh_trader.control import ControlComponent
from ssh_trader.guidance import GuidanceComponent
from ssh_trader.live import LiveComponent
from ssh_trader.nav import NavComponent
from ssh_trader.risk import RiskComponent


class Describable(Protocol):
    def describe(self) -> str: ...


def test_placeholder_components_describe() -> None:
    components: list[Describable] = [
        NavComponent(),
        GuidanceComponent(),
        ControlComponent(),
        RiskComponent(),
        BacktestComponent(),
        LiveComponent(),
    ]

    assert all(component.describe().endswith("placeholder subsystem") for component in components)
