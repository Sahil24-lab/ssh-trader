# TA-04 — 4H bias + triggers

## Title
TA-04 — Higher-timeframe (4H) bias filter and deterministic triggers

## Objective
Implement:

- 4H trend/bias filter (EMA-based)
- Trigger rules to transition from “compression” to “entry intent”

## In Scope / Out of Scope

### In scope
- 4H bias filter:
  - `EMA20_4H > EMA50_4H` and price above EMA20_4H → UP
  - symmetric for DOWN
  - else FLAT
- Trigger Type A (MVP): breakout close + follow-through
- Optional: retest entry variant (documented, behind config)

### Out of scope
- Sweep + reclaim triggers (later)
- Multi-candle candlestick pattern library (later)

## Functional Requirements

1. **Bias classification**
   - Compute EMA20 and EMA50 on 4H close.
   - Compute bias per 4H bar: `UP`/`DOWN`/`FLAT`.
   - Bias used to gate trades:
     - only longs if bias == UP
     - only shorts if bias == DOWN

2. **Trigger A — breakout close**
   Long breakout above resistance band:
   - `close > R + x*ATR14` (x configurable)
   - CLV `(close-low)/(high-low) > clv_threshold` (default 0.7)
   - Optional follow-through: next candle doesn’t close back below R
   - Symmetric short rules for support

3. **Optional entry variant — breakout then retest**
   - After breakout trigger, place a “pending” entry:
     - limit at `R + buffer` for long (buffer configurable, ATR-based or bps)
     - valid for `retest_max_bars`
   - Invalidate on:
     - price closes back inside the band by a configured threshold
     - time-out without fill
   - Document clearly as more realistic but fewer fills.

## Non-Functional Requirements
- Deterministic and backtest-safe (no intrabar assumptions beyond chosen fill model).

## Interfaces / Artifacts

### New modules
- `src/ssh_trader/ta/bias.py`
- `src/ssh_trader/ta/triggers.py`

### Config
- `BiasConfig`
- `TriggerConfig`
- `RetestConfig` (optional)

### Trigger outputs
- `TriggerEvent` record including:
  - `side`, `strength`, `clv`, `breakout_distance_atr`
  - `level_id` / band
  - `reason` if not triggered

## Implementation Notes
- Map 1H bars to the “current” 4H bias deterministically (by timestamp bucket).
- Keep one trigger type enabled for MVP to avoid blending logic.

## Tests
- Bias test on known 4H series (EMA relationships).
- Breakout trigger pass/fail tests with crafted candles.
- Retest pending logic (timeout/invalidation) tests.

## Acceptance Criteria
- Bias gates long/short as specified.
- Trigger emits deterministic TriggerEvents and reason codes.

## Follow-ups / Future Extensions
- Add Trigger B (sweep + reclaim) as a separate config mode.
