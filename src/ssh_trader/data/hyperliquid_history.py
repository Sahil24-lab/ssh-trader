from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib import request

_INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
    "1M": 2_592_000_000,
}

_MAX_CANDLES_PER_REQ = 5000
_MAX_FUNDING_EVENTS_PER_REQ = 5000


@dataclass(frozen=True, slots=True)
class HistoryRow:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    funding: float
    open_interest: float


def parse_time_ms(value: str) -> int:
    s = value.strip()
    if s.isdigit():
        return int(s)
    dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    return int(dt.timestamp() * 1000)


def _http_post_json(base_url: str, payload: dict[str, Any], timeout_s: float) -> Any:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/info",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _as_float(raw: Any, *, default: float = 0.0) -> float:
    if raw is None:
        return default
    if isinstance(raw, int | float):
        val = float(raw)
    else:
        val = float(str(raw))
    if not math.isfinite(val):
        return default
    return val


def _as_int(raw: Any, *, default: int = 0) -> int:
    if raw is None:
        return default
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    s = str(raw)
    if s.isdigit():
        return int(s)
    return default


def _parse_candle(item: dict[str, Any]) -> tuple[int, float, float, float, float, float]:
    ts_ms = _as_int(item.get("t"))
    if ts_ms == 0:
        ts_ms = _as_int(item.get("T"))
    if ts_ms == 0:
        ts_ms = _as_int(item.get("time"))
    if ts_ms == 0:
        ts_ms = _as_int(item.get("timestamp"))
    if ts_ms == 0:
        raise ValueError("unable to parse candle timestamp")

    o = _as_float(item.get("o", item.get("open")))
    h = _as_float(item.get("h", item.get("high")))
    low_value = _as_float(item.get("l", item.get("low")))
    c = _as_float(item.get("c", item.get("close")))
    v = _as_float(item.get("v", item.get("volume")))
    return ts_ms, o, h, low_value, c, v


def fetch_candles(
    *,
    base_url: str,
    coin: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    timeout_s: float = 15.0,
) -> list[tuple[int, float, float, float, float, float]]:
    if interval not in _INTERVAL_MS:
        raise ValueError(f"unsupported interval: {interval}")
    out: list[tuple[int, float, float, float, float, float]] = []

    step_ms = _INTERVAL_MS[interval]

    # Hyperliquid only serves ~5000 candles per interval (rolling window).
    # If the requested window is older than what the API retains, clamp to the earliest available
    # so we still return the overlapping portion instead of silently returning nothing.
    now_ms = int(time.time() * 1000)
    earliest_ms = now_ms - (step_ms * _MAX_CANDLES_PER_REQ)

    # If the entire requested window ends before retention starts, nothing can be returned.
    if end_ms <= earliest_ms:
        return []

    cursor = max(start_ms, earliest_ms)

    while cursor < end_ms:
        chunk_end = min(end_ms, cursor + step_ms * _MAX_CANDLES_PER_REQ)
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
                "startTime": cursor,
                "endTime": chunk_end,
            },
        }
        data = _http_post_json(base_url, payload, timeout_s)
        if isinstance(data, dict):
            # Hyperliquid sometimes returns structured errors as objects.
            raise ValueError(f"candleSnapshot error: {data}")
        if not isinstance(data, list):
            raise ValueError(f"unexpected candleSnapshot response type: {type(data)}")
        chunk: list[tuple[int, float, float, float, float, float]] = []
        for row in data:
            if isinstance(row, dict):
                chunk.append(_parse_candle(row))
        if not chunk:
            # No candles in this window: advance by one chunk.
            cursor = chunk_end
            continue
        chunk.sort(key=lambda x: x[0])
        out.extend(chunk)
        last_ts = chunk[-1][0]
        nxt = last_ts + step_ms
        if nxt <= cursor:
            break
        cursor = nxt
        # API docs mention 5000-candle availability. stop if we already reached end.
        if last_ts >= end_ms - step_ms:
            break
    # Deduplicate timestamps.
    dedup: dict[int, tuple[int, float, float, float, float, float]] = {}
    for row in out:
        dedup[row[0]] = row
    rows = [dedup[k] for k in sorted(dedup.keys()) if start_ms <= k <= end_ms]
    return rows


def fetch_funding_history(
    *,
    base_url: str,
    coin: str,
    start_ms: int,
    end_ms: int,
    timeout_s: float = 15.0,
) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    cursor = start_ms
    while cursor <= end_ms:
        # Funding is typically 8h; request in chunks to avoid server-side limits.
        chunk_end = min(end_ms, cursor + 86_400_000 * 365)  # 1y window (safe default)
        payload = {
            "type": "fundingHistory",
            "coin": coin,
            "startTime": cursor,
            "endTime": chunk_end,
        }
        data = _http_post_json(base_url, payload, timeout_s)
        if isinstance(data, dict):
            raise ValueError(f"fundingHistory error: {data}")
        if not isinstance(data, list):
            raise ValueError(f"unexpected fundingHistory response type: {type(data)}")
        if not data:
            cursor = chunk_end + 1
            continue

        chunk: list[tuple[int, float]] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            ts = _as_int(row.get("time", row.get("t", row.get("timestamp"))))
            if ts == 0:
                continue
            rate = _as_float(row.get("fundingRate", row.get("funding", row.get("rate"))))
            chunk.append((ts, rate))
        if not chunk:
            cursor = chunk_end + 1
            continue
        chunk.sort(key=lambda x: x[0])
        out.extend(chunk)
        last_ts = chunk[-1][0]
        nxt = last_ts + 1
        if nxt <= cursor:
            break
        cursor = nxt
        if len(chunk) >= _MAX_FUNDING_EVENTS_PER_REQ:
            # Likely hit a server-side limit; continue from the last ts.
            continue
        if last_ts >= end_ms:
            break

    dedup: dict[int, float] = {}
    for ts, rate in out:
        dedup[ts] = rate
    return [(k, dedup[k]) for k in sorted(dedup.keys())]


def fetch_latest_open_interest(
    *,
    base_url: str,
    coin: str,
    timeout_s: float = 15.0,
) -> float:
    payload = {"type": "metaAndAssetCtxs"}
    data = _http_post_json(base_url, payload, timeout_s)
    if not (isinstance(data, list) and len(data) >= 2):
        return 0.0
    meta = data[0]
    ctxs = data[1]
    if not (isinstance(meta, dict) and isinstance(ctxs, list)):
        return 0.0
    universe = meta.get("universe")
    if not isinstance(universe, list):
        return 0.0

    idx = -1
    for i, item in enumerate(universe):
        if isinstance(item, dict) and str(item.get("name")) == coin:
            idx = i
            break
    if idx < 0 or idx >= len(ctxs):
        return 0.0
    row = ctxs[idx]
    if not isinstance(row, dict):
        return 0.0
    return _as_float(row.get("openInterest"), default=0.0)


def merge_history_rows(
    *,
    candles: list[tuple[int, float, float, float, float, float]],
    funding: list[tuple[int, float]],
    default_open_interest: float = 0.0,
) -> list[HistoryRow]:
    funding_sorted = sorted(funding, key=lambda x: x[0])
    fi = 0
    cur_funding = 0.0
    rows: list[HistoryRow] = []
    for ts, o, h, low_value, c, v in sorted(candles, key=lambda x: x[0]):
        while fi < len(funding_sorted) and funding_sorted[fi][0] <= ts:
            cur_funding = funding_sorted[fi][1]
            fi += 1
        rows.append(
            HistoryRow(
                ts_ms=ts,
                open=o,
                high=h,
                low=low_value,
                close=c,
                volume=v,
                funding=cur_funding,
                open_interest=default_open_interest,
            )
        )
    return rows


def ts_ms_to_utc_iso(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")
