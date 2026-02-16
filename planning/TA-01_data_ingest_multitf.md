# TA-01 — Data ingest (1H + deterministic 4H)

## Title
TA-01 — Multi-timeframe data ingest and normalized store

## Objective
Produce deterministic, gap-checked OHLCV datasets for:

- **Execution timeframe:** 1H
- **Bias timeframe:** 4H (derived via deterministic resample from 1H)

Datasets must be UTC-normalized and suitable for both offline backtests and live paper runs.

## In Scope / Out of Scope

### In scope
- Fetch Hyperliquid candles for `BTC` and `ETH` (configurable symbol list).
- Store normalized 1H candles to `data/`.
- Deterministically resample 1H → 4H and store to `data/`.
- Deterministic gap detection (and optional deterministic filling).
- Simple “sanity report” outputs (counts, missing bars, start/end).

### Out of scope
- Orderbook snapshots (can be added later).
- Full DB storage (CSV is the canonical MVP artifact).
- Live websocket streaming (paper runner will poll).

## Functional Requirements

1. **Inputs**
   - `--coin` (BTC/ETH)
   - `--start`, `--end` (ISO8601 or ms epoch)
   - `--interval 1h`
   - optional `--base-url`

2. **Outputs**
   - `data/hyperliquid_{coin}_1h.csv`
   - `data/hyperliquid_{coin}_4h.csv` (resampled)

3. **UTC normalization**
   - All timestamps stored as ISO8601 with `Z`.
   - Sorted ascending and deduped (keep last).

4. **Gap checks**
   - Verify monotonic timestamps.
   - Detect missing bars and report count.
   - Optional `--fill-missing` to fill deterministically (carry-forward close, zero volume).

5. **4H resample**
   - Use existing `resample_ohlcv` deterministically.
   - Ensure 4H bars are aligned to UTC boundaries (00:00/04:00/08:00/…).

## Non-Functional Requirements
- Deterministic given the same raw candle inputs.
- No secrets in repo; no keys.
- Must run locally for ~5 years of 1H in a reasonable time (target: seconds to tens of seconds).

## Interfaces / Artifacts

### CLI
- Add `scripts/fetch_hyperliquid_multitf.py` (or extend the existing fetch script) with:
  - `--coin`, `--start`, `--end`
  - `--output-dir data/`
  - `--emit-4h` (default true)
  - `--fill-missing` (default false)

### CSV schemas
1H and 4H outputs use the same schema:

`timestamp,open,high,low,close,volume,funding,open_interest`

Notes:
- `funding` and `open_interest` remain optional; if present they must be finite.

## Implementation Notes
- Prefer resampling 4H from 1H to avoid candle-boundary ambiguity and reduce API complexity.
- Keep ingest side effects limited to writing output files and small console summaries.

## Tests
- Resample alignment test:
  - Build a small 1H synthetic series with known OHLC aggregation, resample to 4H, assert values.
- Gap detection test:
  - Provide timestamps with a missing hour and assert missing count.
- UTC normalization test:
  - Provide mixed tz-aware/naive datetimes via CSV load path and assert normalization.

## Acceptance Criteria
- Running the script for a 90+ day window yields non-empty 1H and 4H CSVs.
- 4H timestamps are aligned to UTC boundaries.
- Gap detection reports correct missing counts; `--fill-missing` produces contiguous series.

## Follow-ups / Future Extensions
- Optional direct 4H fetch + cross-check against resampled 4H.
- Add orderbook snapshot capture for slippage modeling.
