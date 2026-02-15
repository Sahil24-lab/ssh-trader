# AGENTS.md — Trading System (GNC)

## Goal

Build a regime-adaptive crypto trading system (70% delta-neutral carry / 30% directional overlay)
targeting:

- Bear: 5–10%
- Neutral: 10–15%
- Bull: 15–50%
  with strict downside protection and permanent leverage cap.

## Non-negotiables (risk)

- Hard leverage cap: <= 1.5x (default 1.0x)
- Per-venue capital cap: <= 30% of portfolio NAV
- Portfolio max drawdown kill switch: 20% (configurable)
- Directional overlay ONLY when regime == RISK_ON
- Must model fees + slippage + funding + liquidation buffers in backtests
- No secrets in repo. Use env vars. Never print keys.

## Architecture

- nav/: state estimation + regime classifier (rule-based or switching state model)
- guidance/: exposure targets (policy) based on regime
- control/: execution + order placement + routing protections
- risk/: limits, sizing, drawdown monitors, circuit breakers
- backtest/: event-driven backtest + metrics
- live/: adapters for venues + paper/shadow mode first

## Work style

- Small tasks, each with:
  1. clear acceptance criteria
  2. tests or a runnable script
  3. documented assumptions
- Prefer deterministic, explainable models over opaque ML.
- If unsure, propose 2–3 options with pros/cons, then implement the simplest that satisfies constraints.

## Validation commands

- `pytest -q`
- `python -m src.backtest.run --config configs/dev.yaml` (create)
- `python -m src.nav.replay --symbol BTC --tf 1h --from 2020-01-01` (create)

## Initial venue assumptions

- Start with Hyperliquid adapter interface.
- Keep venue layer abstract; add more venues later.
