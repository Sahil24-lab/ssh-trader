# TA-07 — Live paper runner (polling)

## Title
TA-07 — Live paper mode loop on 1H candle close

## Objective
Run the deterministic TA/FSM strategy continuously in paper mode:

- Poll for new 1H candles
- Update features/FSM
- Emit intended orders and simulated fills
- Persist state and logs

## In Scope / Out of Scope

### In scope
- Polling (no websockets) once per new 1H candle.
- State persistence to disk (`json`) per symbol.
- Conservative fill simulation (spread/slippage proxy).
- Logging to CSV with reason codes.
- Safety gates (risk per trade, max trades/day, kill switch).

### Out of scope
- Real order signing/execution
- High-frequency behavior or intrabar management

## Functional Requirements

1. **Candle acquisition**
   - Pull latest candles each cycle (Hyperliquid API or cached ingest output).
   - Detect “new bar” by timestamp.

2. **State persistence**
   - Persist FSM state, pending retest orders, last processed timestamp.

3. **Paper fills**
   - Simulate fill using:
     - mid price +/- spread proxy
     - slippage model consistent with backtest

4. **Logging**
   - `out/paper_events.csv`:
     - ts, state, bias, cs, level_id, trigger fields
     - intended_order, simulated_fill, fees/slippage assumptions
     - reason codes

5. **Risk/safety**
   - Configurable risk per trade (USD or % NAV)
   - Hard cap on number of new entries per day
   - Kill switch on drawdown (paper NAV)

## Non-Functional Requirements
- Runs for weeks without crashing.
- Deterministic behavior given identical candle stream.

## Interfaces / Artifacts

### New module
- `src/ssh_trader/ta/paper.py`

### CLI
- `python -m ssh_trader.ta.run_paper --symbol BTC --interval 1h --state out/paper_state.json --log out/paper_events.csv`

## Implementation Notes
- Keep “paper NAV” accounting separate from the existing carry simulator.
- Ensure time handling is UTC and robust to missing bars.

## Tests
- State persistence round-trip.
- “new bar detection” correctness.
- Deterministic event log for a fixed candle stream.

## Acceptance Criteria
- Paper runner produces stable event logs and does not place real orders.

## Follow-ups / Future Extensions
- Add alerting (email/Discord) as a separate module.
