# TA-03 — Compression + confluence score

## Title
TA-03 — Compression detection and confluence scoring

## Objective
Quantify “compression near a level” and compute a confluence score to gate trades.

## In Scope / Out of Scope

### In scope
- ATR compression ratio
- Range contraction measurement
- Near-level check
- Volume/TR confirmation filters
- Confluence score (CS) in [0, 1] + gating threshold

### Out of scope
- Pattern labels (triangle/wedge) as explicit classifiers
- ADX/regime gating (later, if needed)

## Functional Requirements

1. **Compression detection (boolean + degree)**
   - Window W (default 24 bars on 1H)
   - ATR compression: `ATR14 / SMA(ATR14, 50) < atr_ratio_threshold` (default 0.8)
   - Range contraction: rolling range `HH(W)-LL(W)` decreasing (slope negative) over last N windows
   - Near-level: distance to band center <= `near_atr_mult * ATR14` (default 0.5)

2. **Volume / range expansion confirmation**
   - `vol_z = (vol - SMA(vol,50)) / STD(vol,50)` (default confirm: `vol_z > 1.0`)
   - Alternative: TR expansion confirm `TR / SMA(TR,50) > tr_ratio_threshold` (default 1.2)
   - Implement as filter features (don’t hard-code to one; config picks one).

3. **Confluence score**
   - Features scaled 0..1:
     - `f_level`: from TA-02
     - `f_compress`: from compression degree
     - `f_trigger`: from trigger strength (TA-04)
     - `f_volume`: from vol_z/TR expansion
     - `f_bias`: HTF alignment (TA-04)
   - Score:
     - `CS = Σ w_i * f_i` (weights default from spec)
   - Gate:
     - Only emit trade intent if `CS >= cs_threshold` (default 0.7)

## Non-Functional Requirements
- Stable numeric outputs; clamp to [0, 1].
- Deterministic and testable without network.

## Interfaces / Artifacts

### New modules
- `src/ssh_trader/ta/compression.py`
- `src/ssh_trader/ta/confluence.py`

### Config
- `CompressionConfigTA`
- `VolumeConfirmConfig`
- `ConfluenceConfig`

### Reason codes
Add explicit gating reason codes:
- `NO_LEVEL`
- `NOT_NEAR_LEVEL`
- `NO_COMPRESSION`
- `VOLUME_FAIL`
- `CS_FAIL`

## Implementation Notes
- Keep compression indicators robust and simple; avoid excessive parameters.
- Ensure windowing uses only trailing values.

## Tests
- Synthetic contracting range should set compression true.
- Synthetic expanding range should set compression false.
- CS calculation test to ensure correct weighting + clamping.

## Acceptance Criteria
- Compression and CS remain stable on repeated runs.
- “No trade” decisions are explainable via reason codes.

## Follow-ups / Future Extensions
- Add regime gates if chop kills performance.
