# Planning Index — TA-FSM Hyperliquid Bot

This folder contains the PRDs to extend `ssh-trader` into the deterministic TA/FSM system described
in `docs/trading_system_spec.md`.

## Big picture

### Existing modules (today)

- `src/ssh_trader/data/`: CSV IO + cleaning + resample + Hyperliquid history fetch
- `src/ssh_trader/nav/`: regime/vol/trend/compression features + replay
- `src/ssh_trader/guidance/`: regime → target exposures (carry/directional)
- `src/ssh_trader/risk/`: leverage/drawdown/vol-spike governor
- `src/ssh_trader/backtest/`: event-driven portfolio simulator + metrics
- `src/ssh_trader/control/` + `src/ssh_trader/live/`: shadow mode execution abstraction

### New modules to add (target)

Add a parallel TA strategy stack under `src/ssh_trader/ta/` (no removal of existing logic):

- `ta/levels.py`: pivots → level clustering → scoring
- `ta/compression.py`: compression detection (ATR/range contraction/near-level)
- `ta/confluence.py`: confluence scoring + gate
- `ta/bias.py`: 4H bias filter (EMA20/EMA50)
- `ta/triggers.py`: breakout / (optional) retest trigger rules
- `ta/fsm.py`: setup detection finite-state machine (S0..S6)
- `ta/signals.py`: signal objects + reason codes
- `ta/backtest.py`: event-driven TA backtest
- `ta/metrics.py`: R-based evaluation metrics
- `ta/paper.py`: live paper loop (poll on 1H close)
- `ta/walkforward.py`: deterministic walk-forward harness

## PRDs

- [TA-01 — Data ingest (1H + deterministic 4H)](TA-01_data_ingest_multitf.md)
- [TA-02 — Levels (pivots + clustering + scoring)](TA-02_levels_pivots.md)
- [TA-03 — Compression + confluence score](TA-03_compression_confluence.md)
- [TA-04 — 4H bias + triggers](TA-04_bias_triggers.md)
- [TA-05 — Strategy FSM + signals](TA-05_fsm_signals.md)
- [TA-06 — Backtest in R + metrics](TA-06_backtest_r_metrics.md)
- [TA-07 — Live paper runner](TA-07_live_paper_runner.md)
- [TA-08 — Walk-forward validation](TA-08_walkforward_validation.md)

## Validation checklist (run per PRD)

Run these until green before moving to the next PRD:

```bash
pytest -q
ruff check .
python -m black --check .
mypy src tests
```

Optional (matches pre-commit):

```bash
pre-commit run --all-files
```

## Definition of Done (for each PRD)

- Pure functions are deterministic (no randomness, no wall-clock dependence)
- Clear reason codes for “no trade” / invalidations
- No future leakage (unit tests cover key leakage risks)
- CLI produces stable artifacts (CSV schemas explicitly documented)
- `pytest`, `ruff`, `black --check`, `mypy` all pass
