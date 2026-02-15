# PLANS.md

## Milestone 1: Research harness (no trading)

- Data model + storage (candles, funding, OI, volume)
- Navigation:
  - realized vol + vol percentile
  - trend filter (e.g., 100/200D)
  - regime state machine {RISK_OFF, NEUTRAL, RISK_ON}
  - compression score + expansion trigger (physics-inspired feature)
- Replay tool to visualize regime over history
- Unit tests for indicators + regime transitions

## Milestone 2: Portfolio sim

- Guidance policy mapping regime -> target exposures
- Carry engine simulator (spot/perp hedged funding capture)
- Directional overlay simulator (only RISK_ON)
- Portfolio PnL with fees/slippage/funding

## Milestone 3: Execution + live shadow mode

- Control layer interface
- Hyperliquid paper/shadow adapter
- Risk governor + kill switch
- Logging/metrics + daily report
