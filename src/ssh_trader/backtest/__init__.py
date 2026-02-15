"""backtest domain for the ssh-trader GNC stack."""

from .metrics import Metrics, compute_metrics
from .module import BacktestComponent
from .simulator import (
    BarResult,
    FeeModel,
    PortfolioState,
    SimulationResult,
    SimulatorConfig,
    SlippageModel,
    TradeEvent,
    simulate_portfolio,
)

__all__ = [
    "BacktestComponent",
    "BarResult",
    "FeeModel",
    "Metrics",
    "PortfolioState",
    "SimulationResult",
    "SimulatorConfig",
    "SlippageModel",
    "TradeEvent",
    "compute_metrics",
    "simulate_portfolio",
]
