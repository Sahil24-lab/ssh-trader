# TA-08 — Walk-forward validation harness

## Title
TA-08 — Deterministic walk-forward validation (train/test splits)

## Objective
Prevent overfitting by enforcing a walk-forward workflow:

- Pick parameters on a train window
- Freeze parameters
- Evaluate on a test window
- Record everything deterministically

## In Scope / Out of Scope

### In scope
- Time-based splits (JSON file or CLI args).
- Small bounded parameter grid search (explicitly limited).
- Output per-split metrics and selected params.
- Deterministic selection logic.

### Out of scope
- Bayesian optimization / large hyperparameter search
- ML models

## Functional Requirements

1. **Splits**
   - Input splits JSON: list of `{train_start, train_end, test_start, test_end}`.
   - Validate non-overlapping time ranges and ordering.

2. **Param search**
   - Define a bounded grid (small) over key thresholds:
     - cs_threshold
     - atr_ratio_threshold
     - breakout_atr_mult
     - vol_z_threshold / tr_ratio_threshold
     - retest_max_bars (if enabled)
   - Scoring metric (default):
     - maximize EV(R) with drawdown constraint

3. **Outputs**
   - `out/wf_summary.csv` (per split)
   - `out/wf_params.json` (chosen params per split)
   - Optional full grid results `out/wf_grid.csv`

## Non-Functional Requirements
- Deterministic: same inputs → same best params.
- Bounded compute time.

## Interfaces / Artifacts

### New module
- `src/ssh_trader/ta/walkforward.py`

### CLI
- `python -m ssh_trader.ta.run_walkforward --symbol BTC --csv-1h ... --csv-4h ... --splits splits.json --out out/`

## Implementation Notes
- Enforce strict caps on the number of param combinations.
- Always write “attempt log” of param combos for auditability.

## Tests
- Split parsing/validation tests.
- Deterministic best-param selection on toy data.

## Acceptance Criteria
- Produces stable summary artifacts and enforces train/test separation.

## Follow-ups / Future Extensions
- Add regime segmentation to analyze performance by market regime.
