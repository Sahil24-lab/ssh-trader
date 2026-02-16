# Context: Hyperliquid TA Bot (1H/4H) — System Spec

## Goal

Build a deterministic, testable trading system (not an LLM-driven vibes bot) that:

- Ingests Hyperliquid market data (OHLCV candles; optional orderbook/funding/OI).
- Detects higher-timeframe TA setups (1H entries with 4H bias).
- Backtests and validates statistically (expectancy in R, drawdown, regime dependence).
- Runs live in paper/sim mode first, then small-cap deployment ($1K) with strict risk controls.

Core premise: convert discretionary TA (S/R + compression + candlestick trigger + volume confirmation + 2:1 R:R) into quantifiable rules that can be coded and validated.

---

## High-Level Architecture

Pipeline: **Ingest → Normalize/Store → Feature Extract → Setup Detection (FSM) → Signal → Execution/Sim → Logging/Metrics → Alerts**

Recommended minimal components:

1. **Data Ingestor** (Hyperliquid)
2. **Strategy Engine** (deterministic rules)
3. **Backtest Engine** (offline evaluation)
4. **Paper Trader** (live simulated fills)
5. **Executor** (real trades, later)
6. **Metrics & Reporting** (R-based performance)

Avoid: “monitor everything” or “LLM decides trades.” LLM can be used only for summarization/reporting later.

---

## Data Requirements (Minimum)

For each symbol:

- Candles: **1H** and **4H** OHLCV
- Volume: from candles
  Optional:
- Orderbook snapshots (for slippage modeling / liquidity filter)
- Funding rate (avoid extreme funding regimes)
- Open interest (if available / useful)

Start with majors only:

- BTC, ETH (optionally SOL later)
  Avoid low-liquidity alts initially (they break 2R systems via slippage/whipsaw).

---

## Strategy: State Machine (FSM)

The strategy is best enforced via a finite state machine to prevent trading in chop.

States:

- **S0 NoTrade**: No valid setup.
- **S1 LevelIdentified**: A key S/R level is detected and scored as valid.
- **S2 Compression**: Volatility/range compressing near a level.
- **S3 Trigger**: A defined trigger event occurs (breakout close or sweep+reclaim).
- **S4 Entered**: Position opened with fixed stop and TP.
- **S5 Manage**: Optional management rules (partials, trailing, time stop).
- **S6 Exit**: Trade closed (TP/SL/invalidation).

Allowed transitions:

- S0 → S1 → S2 → S3 → S4 → S6 (MVP; skip S5 initially)
- Any state → S0 if invalidation occurs

MVP focus: **Compression → Breakout** in direction of HTF trend.

---

## Quantifying Support/Resistance Levels

Objective: replace “looks like a level” with measurable rules.

### Pivot Detection

On chosen timeframe (usually 1H for level derivation; optionally 4H):

- Pivot High at t if high[t] is max over window (t-k…t+k), k=2..5
- Pivot Low similarly

### Level Clustering

Cluster pivot prices into bands:

- Band width = `band = 0.3 * ATR14` (or bps-based)
  A level is “valid” if:
- `touch_count >= 3`
- touches separated by at least `min_separation` candles (avoid noise)
- optionally: reactions move away by >= some ATR fraction

### Level Scoring

Compute:

- Touch count
- Recency weighting
- Reaction strength (avg move away after touch, in ATR)
  Normalize to 0..1 and keep top N levels.

---

## Quantifying Compression (Triangle/Wedge/Range)

Don’t overfit classical labels. Use robust compression indicators.

Window W (example: 24 candles on 1H):
Compression is true if:

1. **ATR compression**:
   - `ATR14 / SMA(ATR14, 50) < 0.8` (starting point)
2. **Range contraction**:
   - rolling range (HH(W)-LL(W)) slope is negative over last 2–3 windows
3. **Near level**:
   - price within `d = 0.5 * ATR14` of level band

If true: transition to **S2 Compression**.

---

## Triggers (Candlestick Logic as Quant)

Pick ONE trigger style for MVP. Do not mix.

### Trigger Type A: Breakout Close + Follow-Through (MVP)

For long breakout above resistance R:

- `close[t] > R + x*ATR14` (x ~ 0.05–0.15)
- close-location-value (CLV) high:
  - `(close-low)/(high-low) > 0.7`
    Optional confirmation:
- next candle does not close back below R (anti-fakeout)

For shorts: symmetric rules below support.

### Trigger Type B (Later): Sweep + Reclaim

For long at support S:

- wick below S by w = 0.1–0.3\*ATR14
- close back above S
- wick dominance: lower_wick/body > threshold (e.g. 1.5)

MVP recommendation: start with Trigger A only.

---

## Volume / Range Expansion Confirmation

Volume is noisy; use relative metrics.

Compute:

- `vol_z = (vol - SMA(vol,50)) / STD(vol,50)`
  Confirm breakout with either:
- `vol_z > 1.0` OR
- True-range expansion: `TR / SMA(TR,50) > 1.2`

Use as a filter; don’t rely on absolute volume.

---

## Higher Timeframe Bias (4H Trend Filter)

Avoid fighting regime.

Example:

- Trend Up if `EMA20_4H > EMA50_4H` and price above EMA20_4H
- Trend Down similarly

Rules:

- Only take longs if HTF trend up
- Only take shorts if HTF trend down
- Optional: allow counter-trend only with stricter confluence threshold (later)

---

## Confluence Score (Replace “Feels Clean”)

Convert signals into a numeric gate to reduce overtrading.

Features scaled 0..1:

- f_level: level quality score
- f_compress: degree of compression (ATR ratio / range slope)
- f_trigger: breakout strength (distance beyond level + CLV)
- f_volume: vol_z clipped/scaled
- f_bias: HTF alignment (1 aligned else 0)

Confluence:

- `CS = 0.25*f_level + 0.20*f_compress + 0.25*f_trigger + 0.15*f_volume + 0.15*f_bias`

Trade only if:

- `CS >= 0.7` (starting point; must be validated)

---

## Risk Model (Non-Negotiable)

- Risk per trade: 1%–3% of account (start at 1% for live)
- R:R minimum: **2:1**
- Hard stop and hard TP at order placement
- No discretionary “widen stop”

### Break-even win rate

At TP = 2R, SL = 1R:

- breakeven p ≈ 33.3% ignoring fees
- with costs, need ~37%+ win rate (depends on fee/slippage)

Track everything in **R units**:

- win = +2R
- loss = -1R
- expectancy = avg(R)

---

## Execution & Fill Modeling

MVP backtest assumptions must be conservative:

- Use next candle open or breakout candle close (choose one and be consistent)
- Add slippage model:
  - slippage = max(fixed_bps, k \* ATR fraction)
- Fees modeled explicitly (maker/taker if known)

Prefer:

- **Retest entry** (more robust but fewer fills) as a future variant.
  MVP:
- Breakout close entry for simplicity.

---

## Build Plan (Phased)

### Phase 1: Data Collection (Offline)

- Pull 1H and 4H OHLCV for BTC/ETH from Hyperliquid.
- Store to local CSV/Parquet and/or DB.
- Verify continuity, candle alignment, timezone, missing ranges.

Deliverable:

- `data/{symbol}_{tf}.csv`
- sanity checks (no gaps, monotonic timestamps)

### Phase 2: Offline Backtest Engine

Implement:

- Level detection + clustering
- Compression filter
- Breakout trigger
- HTF bias
- Stop/TP at 1R/2R
  Output:
- Trades list with timestamps, entry/exit, R, reason codes
- Metrics: win rate, EV(R), max DD(R), trade frequency

### Phase 3: Walk-Forward Validation

Split:

- Train window (parameter selection only)
- Test window (no tweaking)
  If performance collapses: overfit → simplify.

### Phase 4: Live Paper Trading

- Run continuously
- Generate signals from live candles
- Simulate fills using orderbook midpoint/spread if available
- Log slippage/fees assumptions vs reality proxies

Minimum: 4–8 weeks.

### Phase 5: Small Live Capital

- $1,000 account
- 1% risk per trade
- Run until >= 100 trades before any conclusion
- Evaluate: EV(R), drawdown, regime stability

---

## Key Constraints (Cost + Noise Control)

- Do NOT scan everything or every coin.
- Start with BTC/ETH only.
- Trade only on 1H triggers with 4H bias.
- Only trade after compression + trigger + confluence threshold.
- Add regime filter if chop causes death (e.g., ATR percentile/ADX gating).

---

## “Success” Criteria (Define Before Building More)

A strategy is considered viable only if, on out-of-sample + paper:

- EV >= +0.05R per trade after costs (example)
- Max drawdown acceptable (e.g. < 15–25R)
- Trade frequency not insane (avoid overtrading)
- Performance doesn’t vanish outside one narrow regime

If it fails:

- simplify rules
- add regime gates
- or kill it

---

## Notes on NanoClaw / Agents

This system does not require an agent runtime.
An agent (NanoClaw) can be used later for:

- orchestration, scheduling, reporting, summarizing weekly results
  But signal generation + execution must remain deterministic and testable.

---

## Implementation Notes (Practical)

- Keep strategy pure and side-effect free:
  - `signals = strategy(candles_1h, candles_4h, params)`
- Separate modules:
  - `ingest/`, `features/`, `strategy/`, `backtest/`, `paper/`, `exec/`, `report/`
- Add reason codes everywhere (debuggability):
  - `NO_LEVEL`, `NO_COMPRESSION`, `TRIGGER_FAIL`, `BIAS_FAIL`, `CS_FAIL`, etc.

---

## Next Tasks (for Codex)

1. Implement candle ingestion for Hyperliquid (1H/4H) with caching and gap checks.
2. Implement ATR/EMA computations and pivot/level detection.
3. Implement FSM + breakout trigger + risk model.
4. Implement offline backtest that outputs trades + summary metrics in R.
5. Implement paper mode loop that runs on candle close, logs decisions, sim fills.
