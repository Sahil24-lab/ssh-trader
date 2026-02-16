# TA-06 — Backtest in R + metrics

## Title
TA-06 — Event-driven TA backtest with R-based reporting

## Objective
Backtest the TA/FSM strategy conservatively and output trade lists and summary metrics in **R units**
and USD.

## In Scope / Out of Scope

### In scope
- Event-driven (bar-by-bar) backtest:
  - one position at a time per symbol (MVP)
  - deterministic fills based on selected entry model
- Risk model:
  - fixed stop = 1R
  - take profit = 2R
- Costs:
  - fees (bps)
  - slippage (conservative model)
- Outputs:
  - `ta_trades.csv`
  - `ta_metrics.csv`
  - optional debug series

### Out of scope
- Multi-position portfolio allocation across symbols (later)
- Intrabar fill modeling with orderbook (later)

## Functional Requirements

1. **Fill model**
   - Choose one and keep consistent:
     - breakout close entry (MVP default)
     - optional retest limit entry
   - Exit logic:
     - stop/TP triggered by subsequent bars (no future leakage)

2. **R accounting**
   - Define R per trade: `R = abs(entry - stop)` in price terms
   - `trade_R` = +2, -1, or intermediate if partial logic later (MVP: only +2 or -1)
   - Track EV(R), win rate, max DD in R, trade frequency.

3. **Costs**
   - Fees:
     - taker fee bps configurable
   - Slippage:
     - `slippage = max(fixed_bps, k * ATR_fraction)` (configurable)
   - Costs must be applied consistently at entry/exit.

4. **Artifacts**
   - `out/ta_trades_{symbol}.csv`:
     - entry_ts, exit_ts, side
     - entry/stop/tp
     - R, pnl_usd, fees_usd, slippage_usd
     - confluence score, reason codes, level id
   - `out/ta_metrics_{symbol}.csv`:
     - win_rate, EV_R, profit_factor, max_DD_R, trades_per_month, avg_hold_bars

## Non-Functional Requirements
- Deterministic outputs for the same input data and params.
- Runs quickly over multi-year 1H data.

## Interfaces / Artifacts

### New modules
- `src/ssh_trader/ta/backtest.py`
- `src/ssh_trader/ta/metrics.py`

### CLI
- `python -m ssh_trader.ta.run_backtest --symbol BTC --csv-1h ... --csv-4h ... --out out/`

## Implementation Notes
- Keep TA strategy pure and feed it into the backtest runner (no embedded IO).
- Emit reason codes for entry/exit (TP/SL/timeout/invalidation).

## Tests
- Fixed synthetic series with one known winning and one known losing trade; assert R outcomes.
- Costs test: ensure fees/slippage reduce pnl deterministically.

## Acceptance Criteria
- `ta_trades.csv` and `ta_metrics.csv` produced and internally consistent.
- No lookahead; tests cover leak-prone sections.

## Follow-ups / Future Extensions
- Portfolio-level aggregation across BTC/ETH with capital allocation (later).
