from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from .model import OHLCVFrame, to_utc_aware


def _pick_col(fieldnames: list[str], candidates: list[str], *, required: bool) -> str | None:
    lowered = {name.lower(): name for name in fieldnames}
    for c in candidates:
        key = c.lower()
        if key in lowered:
            return lowered[key]
    if required:
        raise ValueError(f"missing required column; tried: {candidates}")
    return None


def _parse_timestamp(cell: str) -> datetime:
    s = cell.strip()
    if not s:
        raise ValueError("empty timestamp")

    # Numeric timestamps: seconds or milliseconds since epoch.
    try:
        x = float(s)
    except ValueError:
        x = float("nan")
    if x == x:  # not NaN
        if x > 1e12:
            x /= 1000.0
        return datetime.fromtimestamp(x, tz=timezone.utc)

    # ISO-like timestamps.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    return to_utc_aware(dt)


def load_ohlcv_csv(path: Path) -> OHLCVFrame:
    """Load an OHLCV CSV with timestamp index and optional funding/open interest.

    Required columns (case-insensitive): timestamp, open, high, low, close, volume
    Optional columns: funding, open_interest
    """
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV must have a header row")
        fieldnames = [name for name in reader.fieldnames if name is not None]

        ts_col = _pick_col(fieldnames, ["timestamp", "time", "date", "datetime"], required=True)
        open_col = _pick_col(fieldnames, ["open"], required=True)
        high_col = _pick_col(fieldnames, ["high"], required=True)
        low_col = _pick_col(fieldnames, ["low"], required=True)
        close_col = _pick_col(fieldnames, ["close"], required=True)
        vol_col = _pick_col(fieldnames, ["volume", "vol"], required=True)

        funding_col = _pick_col(
            fieldnames,
            ["funding", "funding_rate", "fundingrate"],
            required=False,
        )
        oi_col = _pick_col(fieldnames, ["open_interest", "openinterest", "oi"], required=False)

        ts: list[datetime] = []
        o: list[float] = []
        h: list[float] = []
        low: list[float] = []
        c: list[float] = []
        v: list[float] = []
        funding: list[float] | None = [] if funding_col is not None else None
        open_interest: list[float] | None = [] if oi_col is not None else None

        for row in reader:
            ts.append(_parse_timestamp(row[ts_col]))
            o.append(float(row[open_col]))
            h.append(float(row[high_col]))
            low.append(float(row[low_col]))
            c.append(float(row[close_col]))
            v.append(float(row[vol_col]))

            if funding_col is not None and funding is not None:
                cell = (row.get(funding_col) or "").strip()
                funding.append(float(cell) if cell else 0.0)
            if oi_col is not None and open_interest is not None:
                cell = (row.get(oi_col) or "").strip()
                open_interest.append(float(cell) if cell else 0.0)

        return OHLCVFrame(
            ts=ts,
            open=o,
            high=h,
            low=low,
            close=c,
            volume=v,
            funding=funding,
            open_interest=open_interest,
        )
