# ssh-trader

`ssh-trader` is a regime-adaptive crypto trading system built with a GNC
(Navigation, Guidance, Control) architecture plus explicit risk, backtest, and
live/shadow execution layers.

## 5-minute quickstart

This is the fastest clean path to get from clone -> run -> dashboard.

### 1) Set up environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -e '.[dev]'
```

If you are in a restricted/offline environment:

```bash
pip install -e '.[dev]' --no-build-isolation
```

### 2) Validate install

```bash
bash scripts/validate.sh
```

### 3) Run the full pipeline (recommended)

```bash
bash scripts/run_e2e_hyperliquid.sh --coin BTC --interval 1h --lookback-days 180 --out-dir out
```

This runs: fetch -> replay -> backtest -> shadow -> TA features -> dashboard.

### 4) Open outputs

Main artifacts:

- `out/nav_regimes.csv`
- `out/metrics.csv`
- `out/bars.csv`
- `out/trades.csv`
- `out/lifecycle.csv`
- `out/shadow_log.csv`
- `out/ta_features.csv`
- `out/dashboard.html`

Open `out/dashboard.html` directly, or serve it with rerun support:

```bash
.venv/bin/python scripts/serve_dashboard.py --dashboard out/dashboard.html --csv data/hyperliquid_btc_1h.csv
```

Then open `http://127.0.0.1:8000/`.

### 5) Re-run without refetching data

```bash
SKIP_FETCH=1 DATA_CSV=data/hyperliquid_btc_1h.csv bash scripts/run_e2e_hyperliquid.sh
```

## Run each module directly (optional)

### Navigation replay (labels only, no trading)

```bash
.venv/bin/python -m ssh_trader.nav.replay \
  --csv data/hyperliquid_btc_1h.csv \
  --timeframe 1h \
  --fill-missing \
  --output out/nav_regimes.csv
```

### Backtest portfolio simulator

```bash
.venv/bin/python -m ssh_trader.backtest.run \
  --csv data/hyperliquid_btc_1h.csv \
  --timeframe 1h \
  --fill-missing \
  --output-metrics out/metrics.csv \
  --output-bars out/bars.csv \
  --output-trades out/trades.csv \
  --output-lifecycle out/lifecycle.csv
```

The simulator uses the same regime/guidance/risk stack as the dashboard. It now
models directional positions as managed trade lifecycles rather than one-bar
target pulses:

- entries are queued by configurable bar latency and filled inside the execution candle
- exits are explicit (`stop_loss`, `take_profit`, `max_hold`, `regime_invalid`, or risk block)
- lifecycle CSV rows include `exit_reason`
- carry can be disabled by setting all carry allocation bands to `[0, 0]`
- small carry target drift can be ignored with `sim.carry_rebalance_threshold_pct`

Example config snippet:

```json
{
  "guidance": {
    "aggressiveness": 0.5,
    "risk_off_carry": [0, 0],
    "neutral_carry": [0, 0],
    "risk_on_carry": [0, 0]
  },
  "sim": {
    "order_latency_bars": 1,
    "fill_time_fraction": 0.25,
    "fill_range_position": 0.75,
    "directional_stop_loss_pct": 0.02,
    "directional_take_profit_pct": 0.04,
    "directional_max_hold_bars": 24,
    "carry_rebalance_threshold_pct": 0.01
  }
}
```

### Live shadow runner (no signing, no keys)

```bash
.venv/bin/python -m ssh_trader.live.shadow_runner \
  --csv data/hyperliquid_btc_1h.csv \
  --timeframe 1h \
  --fill-missing \
  --output out/shadow_log.csv
```

### TA feature dump

```bash
.venv/bin/python scripts/dump_ta_features.py \
  --csv-1h data/hyperliquid_btc_1h.csv \
  --csv-4h data/hyperliquid_btc_4h.csv \
  --fill-missing \
  --output out/ta_features.csv
```

## Hyperliquid historical CSV fetch

```bash
.venv/bin/python scripts/fetch_hyperliquid_multitf.py \
  --coin BTC \
  --start 2024-01-01T00:00:00Z \
  --end 2024-06-01T00:00:00Z \
  --output-dir data \
  --fill-missing
```

Output files:

- `data/hyperliquid_btc_1h.csv`
- `data/hyperliquid_btc_4h.csv`

Notes:

- `timestamp` is UTC ISO8601 (`...Z`).
- Hyperliquid 1h history is limited to roughly the most recent ~5000 candles.
- For stable warm-up of long-window features, `--lookback-days 180` is a good default.

## Development checks

```bash
bash scripts/validate.sh
pre-commit run --all-files
pre-commit run --hook-stage pre-push --all-files
```

If PATH resolution is noisy, prefer explicit interpreter:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy src tests
.venv/bin/python -m ruff check .
.venv/bin/python -m black --check .
```

## Run the interactive dashboard

The Next.js dashboard is in `trading-dashboard/`. Use Node 20+; the local build
has been verified with Node 22.

```bash
cd trading-dashboard
npm install
npm run dev
```

Then open `http://127.0.0.1:3000/dashboard`.

If your shell resolves an older Node version, use the project Node 22 path:

```bash
PATH=/Users/sahil/.nvm/versions/node/v22.21.1/bin:$PATH npm run dev
```

From the dashboard you can rerun the simulation against `data/hyperliquid_btc_1h.csv`,
toggle carry on/off, and adjust execution assumptions, directional stop/take-profit,
max hold, and carry rebalance threshold.

## Security note

- Never commit secrets. Use environment variables.
- Do not print API keys in logs or CLI output.
- Use shadow mode first before any live venue integration.

## Architecture

- `src/ssh_trader/nav`: state estimation + regime labels
- `src/ssh_trader/guidance`: exposure targets/policy
- `src/ssh_trader/control`: execution decisions + routing protections
- `src/ssh_trader/risk`: hard limits, sizing, drawdown kill-switch logic
- `src/ssh_trader/backtest`: event-driven simulation and metrics
- `src/ssh_trader/live`: venue adapters + shadow execution

Architecture docs:

- `docs/architecture.html`
- `docs/architecture.graph.json`
- `docs/architecture.mmd`
- `docs/architecture.mermaid.html`

Regenerate Mermaid artifacts after architecture changes:

```bash
python scripts/generate_architecture_diagram.py
```
