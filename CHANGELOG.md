# Changelog

All notable changes to this repository are documented here.

## Unreleased

## 0.1.0 — 2026-02-15

### Navigation (research harness)

- Added pure indicator utilities in `src/ssh_trader/nav/indicators.py`:
  - `log_returns`
  - `realized_volatility` (rolling)
  - `volatility_percentile` (rolling)
  - `sma` / `ema`
  - `atr` (Wilder and SMA smoothing)
  - `drawdown` and `rolling_drawdown`
- Added reusable feature builders in `src/ssh_trader/nav/features.py`:
  - `trend_signal` (SMA/EMA vs price with optional band)
  - `volatility_features_from_close` (returns + RV + vol percentile with proper alignment)
- Implemented a rule-based regime state machine in `src/ssh_trader/nav/regime.py`:
  - States: `RISK_OFF`, `NEUTRAL`, `RISK_ON`
  - Inputs: trend filter, volatility percentile, optional funding-sign modifier
  - Anti-flip confirmation window via `confirm_bars`
  - Conservative immediate `RISK_OFF` trigger on extreme volatility percentiles
- Implemented compression scoring in `src/ssh_trader/nav/compression.py`:
  - `compression_score` combines ATR contraction, range contraction, and low vol percentile
  - `expansion_trigger` detects post-compression breakouts with volatility expansion and trend alignment
- Added deterministic replay CLI in `src/ssh_trader/nav/replay.py`:
  - Loads OHLCV CSV and outputs a regime time series
  - Optional timezone normalization, sorting/deduping, deterministic gap-filling, and resampling
  - Optional JSON config and optional feature columns (`--include-features`)

### Data model and cleaning

- Added a typed, UTC-normalized time-series data model in `src/ssh_trader/data/model.py` (`OHLCVFrame`, `Timeframe`, parsing helpers).
- Added CSV ingestion for OHLCV (+ optional funding/open interest) in `src/ssh_trader/data/io_csv.py`.
- Added deterministic cleaning utilities in `src/ssh_trader/data/clean.py`:
  - `normalize_and_sort` (UTC normalize, stable sort, dedupe by keeping last)
  - `fill_missing_intervals` (synthetic bars with zero volume and carry-forward close)
- Added resampling utilities in `src/ssh_trader/data/resample.py` (OHLCV bucket aggregation, funding mean, OI last).

### Tests and reproducibility

- Added unit tests with fixed inputs:
  - `tests/test_indicators.py`
  - `tests/test_regime.py`
  - `tests/test_compression.py`
  - `tests/test_data_layer.py`
- Ensured `mypy src tests` passes under strict mypy settings (including explicit typing and avoiding problematic defaults).

### Developer tooling

- Added one-command validation script `scripts/validate.sh` (pytest + mypy + ruff/black when installed), preferring `.venv/bin/python` to avoid conda/PATH conflicts.
- Added GitHub Actions validation workflow `.github/workflows/validate.yml` (pytest + mypy + ruff + black).
- Updated `README.md` with setup, replay usage, and validation workflow guidance.
