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
python -m pip install -U pip setuptools wheel
pip install -e '.[dev]'
pre-commit install
```

If you’re in a restricted/offline environment where pip can’t download build dependencies, use:

```bash
pip install -e '.[dev]' --no-build-isolation
```

## Quick checks

```bash
pytest -q
ruff check .
python -m black --check .
mypy src tests
```

## One-command validation (recommended)

Run the full local validation suite (tests + type-check + format/lint if installed):

```bash
bash scripts/validate.sh
```

If you have multiple Python tools installed (conda/pyenv/system), prefer these to avoid PATH conflicts:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m black --check .
.venv/bin/python -m mypy src tests
.venv/bin/python -m pytest -q
```

To run the same checks via pre-commit (matches `.pre-commit-config.yaml`):

```bash
pre-commit run --all-files
```

## Navigation replay (no trading)

Replay regime labels from an OHLCV CSV (UTC timestamps recommended):

```bash
python -m ssh_trader.nav.replay --csv data/btc_1h.csv --timeframe 1h --fill-missing
```

Optional resampling and feature output:

```bash
python -m ssh_trader.nav.replay --csv data/btc_1h.csv --timeframe 1h --resample 4h --include-features
```

Optional JSON config:

```json
{
  "data": {"timeframe": "1h", "fill_missing": true, "resample": "4h"},
  "regime": {"trend_method": "sma", "long_ma_window": 200, "rv_window": 20, "vol_percentile_window": 252, "confirm_bars": 3}
}
```

## PRD workflow (how to validate each PRD)

For each PRD you generate:

1. Add/adjust pure, deterministic functions under `src/ssh_trader/nav/` and/or `src/ssh_trader/data/`.
2. Add unit tests with fixed inputs under `tests/` (avoid network calls, randomness, and wall-clock time).
3. Run `bash scripts/validate.sh` until green.
4. If you use git, keep pre-commit enabled so `mypy`/formatting can’t regress.
