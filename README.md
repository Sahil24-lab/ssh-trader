# ssh-trader

`ssh-trader` is a Python codebase for a regime-adaptive crypto trading system organized around a
GNC (Navigation, Guidance, Control) architecture with explicit risk and execution layers.

## GNC architecture

- **Navigation (`nav/`)**: Builds market state estimates and regime labels (e.g., `RISK_ON`,
  `NEUTRAL`, `RISK_OFF`).
- **Guidance (`guidance/`)**: Converts state estimates into target exposures and portfolio policy.
- **Control (`control/`)**: Translates targets into executable orders and applies venue routing
  protections.
- **Risk (`risk/`)**: Enforces limits (leverage, concentration, drawdown kill-switches), sizing,
  and circuit breakers.
- **Backtest (`backtest/`)**: Event-driven simulation stack including fee, slippage, and funding
  assumptions.
- **Live (`live/`)**: Broker/venue adapters and paper/shadow execution paths.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pre-commit install
```

## Quick checks

```bash
pytest -q
ruff check .
black --check .
mypy src tests
```
