# Changelog

All notable changes to this repository are documented here.

## Unreleased

- Fixed backtest NAV accounting for perp positions by marking perps to cash PnL each bar (instead of
  incorrectly treating perps like spot notional), stabilizing NAV/leverage charts and avoiding
  spurious early kill-switch triggers (`src/ssh_trader/backtest/simulator.py`).
- Improved HTML dashboard interactivity and readability:
  - values rounded to 3dp
  - richer hover tooltips (NAV/leverage + attribution fields)
  - smarter time-axis labels when zooming
  - exposure (%NAV) chart and trade/bar-PnL coloring
  - "Rerun Simulation" command generator panel
  - trade markers on charts + regime-change dots (`scripts/build_dashboard.py`)
- Increased default E2E Hyperliquid lookback window to 180 days for more stable feature warmup and
  more informative results (`scripts/run_e2e_hyperliquid.sh`).
- Added TA-01 multi-timeframe data ingest for Hyperliquid (1H candles + funding) with deterministic
  missing-bar fill and deterministic 4H resample output (`scripts/fetch_hyperliquid_multitf.py`).
- Added gap-counting utility for interval integrity checks (`src/ssh_trader/data/gaps.py`) with unit
  tests (`tests/test_data_gaps.py`).
- Added deterministic CSV resample helper (`scripts/resample_ohlcv_csv.py`) and TA feature inspection
  dump (`scripts/dump_ta_features.py`, output `out/ta_features.csv`).
- Rewired the end-to-end runner to use the TA-01 pipeline and emit TA inspection artifacts
  (`scripts/run_e2e_hyperliquid.sh`).
- Added TA-02 levels/pivots module with deterministic pivot detection, band clustering, scoring, and
  per-bar nearest-level proximity (`src/ssh_trader/ta/levels.py`).
- Wired TA-02 levels into TA feature dump with proximity columns in `out/ta_features.csv`
  (`scripts/dump_ta_features.py`).
- Added TA-02 unit tests for pivots, clustering, scoring, and proximity (`tests/test_ta_levels.py`).
- Added trade inspector panel in the dashboard with TA snapshot on trade click; dashboard now loads
  TA features and highlights selected trades on the price chart (`scripts/build_dashboard.py`).
- Added hover tooltips for trade table headers and inspector fields for clearer interpretation
  (`scripts/build_dashboard.py`).
- Added TA features passthrough to the local dashboard API server (`scripts/serve_dashboard.py`).
- Updated documentation for the new fetch/E2E workflow (`README.md`).

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

### PRD 2 — Portfolio simulator & guidance policy

- Added deterministic guidance policy mapping regime → allocation bands in `src/ssh_trader/guidance/policy.py`.
- Added risk governor in `src/ssh_trader/risk/governor.py` enforcing drawdown kill-switch and vol-spike de-risk (directional gating).
- Added event-driven portfolio simulator in `src/ssh_trader/backtest/simulator.py`:
  - carry engine (spot long + perp short), funding accrual, fees + slippage, liquidation buffer via effective leverage cap
  - directional overlay gated by `Regime == RISK_ON` and compression expansion trigger
  - hard leverage cap enforcement (including post-trade enforcement after costs)
- Added backtest metrics in `src/ssh_trader/backtest/metrics.py` (CAGR, Sharpe, Sortino, max drawdown, win rate, exposure utilization, regime returns, funding/directional contribution).
- Added runner CLI `src/ssh_trader/backtest/run.py` to simulate from OHLCV CSV and emit metrics.
- Added unit tests: `tests/test_backtest_simulator.py`, `tests/test_guidance_policy.py`, `tests/test_risk_governor.py`.

## 0.2.0 — 2026-02-15

- Added deterministic guidance policy that maps `Regime` labels to configurable allocation bands (`src/ssh_trader/guidance/policy.py`).
- Added configurable risk governor enforcing drawdown kill switches, directional gating, venue caps, and leverage caps (`src/ssh_trader/risk/governor.py`).
- Added an event-driven portfolio simulator with carry engine, directional overlay, funding, fees/slippage, liquidation buffer enforcement, and trade logging (`src/ssh_trader/backtest/simulator.py`).
- Added performance metrics collection (CAGR, Sharpe, Sortino, drawdown, regime returns, funding vs directional contributions) (`src/ssh_trader/backtest/metrics.py`).
- Added CLI runner to replay OHLCV data through the simulator and emit metrics (`src/ssh_trader/backtest/run.py`).
- Documented simulator usage/tests in README and added CHANGELOG entry.

## 0.3.0 — 2026-02-15

- Added venue execution abstraction with required interface methods in `src/ssh_trader/live/venue.py`.
- Added Hyperliquid shadow adapter stub with simulated responses, configurable latency, and configurable slippage in `src/ssh_trader/live/hyperliquid_stub.py`.
- Added control engine with rebalance scheduling, order sizing, slippage guard, MEV-aware routing placeholder, and partial-fill carryover in `src/ssh_trader/control/engine.py`.
- Added shadow runner that produces intended orders and hypothetical fills without signing/keys in `src/ssh_trader/live/shadow_runner.py`.
- Added refusal controls for leverage cap, drawdown/kill-switch mode, volatility spike gating, and oracle divergence thresholds via control+risk integration.
- Added tests for stub behavior, control refusals/partial fills, and shadow logging in `tests/test_hyperliquid_stub.py`, `tests/test_control_engine.py`, and `tests/test_shadow_runner.py`.

## 0.4.0 — 2026-02-15

- Added Hyperliquid historical data fetch module in `src/ssh_trader/data/hyperliquid_history.py` with:
  - candle snapshot retrieval
  - funding history retrieval
  - UTC timestamp normalization
  - merged output rows with schema `timestamp,open,high,low,close,volume,funding,open_interest`
- Added CLI fetch script `scripts/fetch_hyperliquid_history.py`.
- Added backtest bars export in `src/ssh_trader/backtest/run.py` via `--output-bars` for downstream visualization.
- Added modern dark-mode, self-contained report builder in `scripts/build_dashboard.py` for NAV/leverage/metrics/shadow outcomes.
- Added tests for time parsing/funding merge behavior in `tests/test_hyperliquid_history.py`.
