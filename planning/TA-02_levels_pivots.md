# TA-02 — Levels (pivots + clustering + scoring)

## Title
TA-02 — Quantified support/resistance levels

## Objective
Replace subjective “looks like a level” with deterministic rules:

- Pivot detection
- Level clustering (bands)
- Level validity rules
- Level scoring + top-N selection

## In Scope / Out of Scope

### In scope
- Pivot high/low detection on a chosen timeframe (default: 4H for levels, 1H for execution).
- Level clustering by band width tied to ATR.
- Level scoring and selection.
- Explainable outputs (touch count, reaction strength, recency).
- Per-bar nearest-level proximity output (distance in ATR and kind).

### Out of scope
- Advanced market structure labels (BOS/CHOCH) (later).
- Multi-level hierarchical clustering (later).

## Functional Requirements

1. **Pivot detection**
   - Pivot High at t if `high[t]` is maximum in window `[t-k, …, t+k]`.
   - Pivot Low similarly.
   - Configurable `k` (default 3).
   - Must support deriving pivots from 4H while later systems trade on 1H.

2. **Level banding**
   - Band width: `band = band_atr_mult * ATR14`
   - A pivot price belongs to an existing band if within `band`.
   - Otherwise create a new band.

3. **Validity rules**
   - `touch_count >= 3` (configurable)
   - touches separated by `min_separation_bars` (configurable)
   - reaction strength threshold (e.g., mean move-away >= `reaction_atr_mult * ATR14`)

4. **Scoring**
   - Components:
     - touch count
     - recency weighting
     - reaction strength (ATR units)
   - Score normalized to [0, 1].
   - Select top N support + top N resistance.

## Non-Functional Requirements
- Fully deterministic (no stochastic clustering).
- Efficient enough to run per bar in paper mode (can cache intermediate state later).

## Interfaces / Artifacts

### New module
- `src/ssh_trader/ta/levels.py`

### Data structures
- `PivotConfig`
- `LevelClusterConfig`
- `LevelScoreConfig`
- `Level` record with:
  - `center`, `band_low`, `band_high`
  - `touch_count`, `touch_indices`
  - `reaction_strength_atr`
  - `score`
  - `kind` (support/resistance)

### Optional debug output (CSV)
- `out/ta_levels_{symbol}.csv` with per-level fields.
- `out/ta_level_proximity_{symbol}.csv` with per-bar nearest level + distance in ATR.

## Implementation Notes
- Use ATR from existing indicator utilities.
- Start with simple banding; avoid “perfect clustering” (overfit risk).
- Ensure the algorithm does not use future bars (no lookahead).
- Inputs should accept `data/*_4h.csv` or precomputed ATR series from `out/ta_features.csv`.

## Tests
- Pivot test on fixed highs/lows with known pivot points.
- Clustering test where pivots clearly form two bands; assert band assignment stable.
- Scoring test where one level has more touches/stronger reactions; assert higher score.

## Acceptance Criteria
- Produces stable top-N levels on repeated runs for the same data.
- Levels include enough metadata to explain “why this is a level”.

## Follow-ups / Future Extensions
- Separate level derivation timeframe (e.g., derive levels from 4H, trade on 1H).
- Volume-weighted reactions (later).
