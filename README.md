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

## Portfolio simulator (no execution)

Run the event-driven portfolio simulator (carry + regime-gated directional overlay) over an OHLCV CSV:

```bash
.venv/bin/python -m ssh_trader.backtest.run --csv data/btc_1h.csv --timeframe 1h --fill-missing
```

Optional JSON config keys (all optional):

```json
{
  "data": {"timeframe": "1h", "fill_missing": true},
  "guidance": {"aggressiveness": 0.5},
  "risk": {"leverage_cap": 1.5, "venue_cap_frac": 0.3, "max_drawdown": 0.2, "kill_switch_action": "carry_only"},
  "nav": {"long_ma_window": 200, "rv_window": 20, "vol_percentile_window": 252, "confirm_bars": 3},
  "compression": {"atr_window": 14, "contraction_lookback": 50, "vol_pct_window": 252, "range_window": 50},
  "sim": {"initial_nav": 1000000.0, "carry_funding_freq_hours": 8, "liquidation_buffer": 0.1, "target_dir_vol": 0.2},
  "fees": {"taker_fee_bps": 5.0, "slippage_bps_at_1x_nav": 10.0}
}
```

## Shadow Mode Runner (no signing, no keys)

Run the execution/control stack in shadow mode. This generates intended orders and hypothetical fills
from live-style bar input without placing real orders:

```bash
.venv/bin/python -m ssh_trader.live.shadow_runner --csv data/btc_1h.csv --timeframe 1h --fill-missing --output shadow_log.csv
```

Key logged fields include:

- `intended_order`
- `hypothetical_fill`
- `slippage_estimate_bps`
- `regime`
- `reason` (skip/refusal reason)

## Hyperliquid Historical Feed -> CSV

Fetch historical **1H** candles + funding from Hyperliquid, fill missing bars deterministically, and
emit a deterministic **4H** resample (UTC-normalized CSVs):

```bash
.venv/bin/python scripts/fetch_hyperliquid_multitf.py \
  --coin BTC \
  --start 2024-01-01T00:00:00Z \
  --end 2024-06-01T00:00:00Z \
  --output-dir data \
  --fill-missing
```

Output columns:

`timestamp,open,high,low,close,volume,funding,open_interest`

Notes:

- `timestamp` is always UTC ISO8601 (`...Z`).
- Hyperliquid 1H history is limited to the most recent ~5000 candles; if you request too large a
  window you may get empty results. Prefer shorter windows (e.g. 30–180 days) for iterative work.
- `open_interest` currently uses a latest-available context snapshot (`--open-interest latest_ctx`)
  and is constant across rows.
- Outputs written by default:
  - `data/hyperliquid_btc_1h.csv`
  - `data/hyperliquid_btc_4h.csv`

## End-to-End Pipeline

One-command flow (fetch 1H+4H -> replay -> backtest -> shadow -> TA feature dump -> dashboard):

```bash
bash scripts/run_e2e_hyperliquid.sh
```

Short command (runs the end-to-end pipeline and serves the dashboard API):

```bash
bash scripts/run_dashboard.sh
```

Useful options:

```bash
bash scripts/run_e2e_hyperliquid.sh \
  --coin BTC \
  --interval 1h \
  --lookback-days 180 \
  --out-dir out
```

Notes:

- If you use a long MA trend filter (e.g. `long_ma_window=200`) and rolling vol percentile windows
  (e.g. `vol_percentile_window=252`) on `1h` data, you generally want **at least ~2–4 weeks** of
  data so the features “warm up” and regime transitions can occur. `--lookback-days 180` is a good
  default for quick sanity checks.

Reuse an existing CSV (skip API fetch):

```bash
SKIP_FETCH=1 DATA_CSV=data/hyperliquid_btc_1h.csv bash scripts/run_e2e_hyperliquid.sh
```

Outputs:

- `out/nav_regimes.csv`
- `out/metrics.csv`
- `out/bars.csv`
- `out/trades.csv`
- `out/shadow_log.csv`
- `out/ta_features.csv`
- `out/dashboard.html`

Dashboard tips:

- Charts support drag-pan, wheel-zoom, and double-click to reset view.
- The dashboard includes a **Rerun Simulation** panel:
  - If you open `out/dashboard.html` directly, it shows a CLI command you can copy/paste.
  - If you want a real **Run Simulation** button (and live leverage/exposure charts),
    serve it locally:

```bash
.venv/bin/python scripts/serve_dashboard.py --dashboard out/dashboard.html --csv data/hyperliquid_btc_1h.csv
```

Then open `http://127.0.0.1:8000/`.

Backtest trades vs open/close:

- The **Backtest Trades** table currently shows *rebalance legs* (spot and perp) per bar,
  not discrete open/close trades. That is why you often see two rows at the same timestamp
  (spot + perp legs).
- Trade grouping into explicit **open/close** lifecycles is now available via the lifecycle
  output CSV and the dashboard lifecycle table (both directional and carry).
- Carry lifecycles are closed/reopened on regime changes to make portfolio transitions visible.
- Directional lifecycles can be sparse if RISK_ON + expansion triggers are rare.

1. Fetch data:

```bash
.venv/bin/python scripts/fetch_hyperliquid_multitf.py --coin BTC --start 2024-01-01T00:00:00Z --end 2024-06-01T00:00:00Z --output-dir data --fill-missing
```

2. Run nav replay:

```bash
.venv/bin/python -m ssh_trader.nav.replay --csv data/hyperliquid_btc_1h.csv --timeframe 1h --fill-missing --output out/nav_regimes.csv
```

3. Run backtest (metrics + bars + lifecycle):

```bash
.venv/bin/python -m ssh_trader.backtest.run --csv data/hyperliquid_btc_1h.csv --timeframe 1h --fill-missing --output-metrics out/metrics.csv --output-bars out/bars.csv --output-trades out/trades.csv --output-lifecycle out/lifecycle.csv
```

4. Run shadow simulation:

```bash
.venv/bin/python -m ssh_trader.live.shadow_runner --csv data/hyperliquid_btc_1h.csv --timeframe 1h --fill-missing --output out/shadow_log.csv
```

5. Build modern dark-mode dashboard:

```bash
.venv/bin/python scripts/build_dashboard.py --title "BTC Hyperliquid Report" --bars out/bars.csv --metrics out/metrics.csv --shadow out/shadow_log.csv --trades out/trades.csv --lifecycle out/lifecycle.csv --ta-features out/ta_features.csv --output out/dashboard.html
```

Open `out/dashboard.html` in your browser.

6. (Optional) Dump TA feature columns for inspection/tuning:

```bash
.venv/bin/python scripts/dump_ta_features.py --csv-1h data/hyperliquid_btc_1h.csv --csv-4h data/hyperliquid_btc_4h.csv --fill-missing --output out/ta_features.csv
```
