# TA-05 — Strategy FSM + signals

## Title
TA-05 — Setup detection finite state machine (S0..S6)

## Objective
Implement the deterministic strategy as an FSM to prevent chop trading and to make every decision
explainable.

## In Scope / Out of Scope

### In scope
- FSM states:
  - S0 NoTrade
  - S1 LevelIdentified
  - S2 Compression
  - S3 Trigger
  - S4 Entered
  - S5 Manage (optional; may be a no-op in MVP)
  - S6 Exit
- Allowed transitions enforced exactly.
- “Any state → S0 on invalidation” rule.
- Reason codes everywhere.
- Signal objects (entry intent, stop, TP, risk).

### Out of scope
- Complex trade management (partials/trailing) (later)

## Functional Requirements

1. **State updates**
   - Evaluate per 1H bar, using:
     - levels (TA-02)
     - compression + confluence gate (TA-03)
     - bias + trigger (TA-04)
   - Maintain FSM state with explicit transition rules.

2. **Signals**
   - When entering S4 (Entered), emit:
     - `side` (long/short)
     - `entry`, `stop`, `tp`
     - `risk_usd` and `R` definition
     - `confluence_score`, level metadata, trigger metadata
   - Persist “pending retest order” state if retest mode enabled.

3. **Reason codes**
   - Include reason codes for:
     - no setup
     - failed gates
     - invalidations
     - timeouts

## Non-Functional Requirements
- No future leakage.
- Deterministic: given the same candles and params, the FSM state series is identical.

## Interfaces / Artifacts

### New modules
- `src/ssh_trader/ta/fsm.py`
- `src/ssh_trader/ta/signals.py`

### Data structures
- `State` enum S0..S6
- `Side` enum
- `ReasonCode` enum (shared across TA stack)
- `Signal` dataclass
- Optional debug series:
  - per-bar `state`, `reason`, `cs`, `bias`, etc.

## Implementation Notes
- Keep a strict boundary between:
  - feature computation (pure)
  - FSM decision (pure)
  - execution/backtest (side effects / event handling)

## Tests
- Synthetic sequence that walks S0→S1→S2→S3→S4→S6 deterministically.
- Invalidation test: any state returns to S0 when invalidated.
- Anti-flip test: ensure no immediate oscillation between adjacent states.

## Acceptance Criteria
- FSM transitions match the allowed graph.
- Every bar has a traceable state and reason.

## Follow-ups / Future Extensions
- Add S5 management rules as separate config block.
