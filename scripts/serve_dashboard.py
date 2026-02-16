#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from ssh_trader.backtest.metrics import compute_metrics
from ssh_trader.backtest.simulator import (
    FeeModel,
    SimulatorConfig,
    SlippageModel,
    simulate_portfolio,
)
from ssh_trader.data.clean import fill_missing_intervals, normalize_and_sort
from ssh_trader.data.io_csv import load_ohlcv_csv
from ssh_trader.data.model import parse_timeframe
from ssh_trader.guidance.policy import GuidancePolicy, GuidancePolicyConfig
from ssh_trader.nav.compression import CompressionConfig
from ssh_trader.nav.regime import Regime, RegimeConfig
from ssh_trader.risk.governor import RiskConfig, RiskGovernor


@dataclass(frozen=True, slots=True)
class ServeConfig:
    root_dir: Path
    dashboard_path: Path
    shadow_path: Path | None
    default_csv: Path
    default_timeframe: str


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length_raw = handler.headers.get("Content-Length")
    if length_raw is None:
        return {}
    length = int(length_raw)
    body = handler.rfile.read(length)
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("json body must be an object")
    return cast(dict[str, Any], data)


def _write_json(handler: BaseHTTPRequestHandler, status: int, obj: object) -> None:
    payload = json.dumps(obj).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _load_frame(*, csv_path: Path, timeframe: str | None, fill_missing: bool) -> object:
    frame = load_ohlcv_csv(csv_path)
    frame, _ = normalize_and_sort(frame)
    if fill_missing:
        tf_seconds = (
            parse_timeframe(timeframe).seconds if timeframe else frame.timeframe_seconds_inferred()
        )
        frame, _ = fill_missing_intervals(frame, tf_seconds)
    return frame


def _as_float(d: dict[str, Any], key: str, default: float) -> float:
    v = d.get(key, default)
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str):
        return float(v)
    return float(default)


def _as_bool(d: dict[str, Any], key: str, default: bool) -> bool:
    v = d.get(key, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    if isinstance(v, int):
        return bool(v)
    return default


def _as_str(d: dict[str, Any], key: str, default: str) -> str:
    v = d.get(key, default)
    return str(v) if v is not None else default


def _serialize_metrics(metrics: object) -> list[dict[str, str]]:
    m = metrics
    m_any = cast(Any, m)
    rows: list[tuple[str, float]] = [
        ("cagr", float(m_any.cagr)),
        ("sharpe", float(m_any.sharpe)),
        ("sortino", float(m_any.sortino)),
        ("max_drawdown", float(m_any.max_drawdown)),
        ("win_rate", float(m_any.win_rate)),
        ("exposure_utilization", float(m_any.exposure_utilization)),
        ("funding_contribution", float(m_any.funding_contribution)),
        ("directional_contribution", float(m_any.directional_contribution)),
    ]
    return [{"metric": k, "value": str(v)} for k, v in rows]


def _serialize_bars(result: object) -> list[dict[str, str]]:
    r_any = cast(Any, result)
    out: list[dict[str, str]] = []
    for b in r_any.bars:
        out.append(
            {
                "timestamp": b.ts.isoformat().replace("+00:00", "Z"),
                "nav": str(b.nav),
                "regime": str(b.regime.value if isinstance(b.regime, Regime) else b.regime),
                "carry_notional": str(b.carry_notional),
                "directional_notional": str(b.directional_notional),
                "gross_exposure": str(b.gross_exposure),
                "leverage": str(b.leverage),
                "pnl_price": str(b.pnl_price),
                "pnl_funding": str(b.pnl_funding),
                "pnl_fees": str(b.pnl_fees),
                "pnl_slippage": str(b.pnl_slippage),
                "kill_switch_active": "1" if b.kill_switch_active else "0",
            }
        )
    return out


def _serialize_trades(result: object) -> list[dict[str, str]]:
    r_any = cast(Any, result)
    out: list[dict[str, str]] = []
    for t in r_any.trades:
        out.append(
            {
                "ts": t.ts.isoformat().replace("+00:00", "Z"),
                "leg": str(t.leg),
                "qty_delta": str(t.qty_delta),
                "price": str(t.price),
                "notional": str(t.notional),
                "fee": str(t.fee),
                "slippage": str(t.slippage),
            }
        )
    return out


def _read_shadow_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if header is None:
            header = [h.strip() for h in line.split(",")]
            continue
        parts = line.split(",")
        row = {header[i]: (parts[i] if i < len(parts) else "") for i in range(len(header))}
        rows.append(row)
    return rows


def _run_backtest(cfg: ServeConfig, body: dict[str, Any]) -> dict[str, object]:
    csv_path = Path(_as_str(body, "csv", str(cfg.default_csv)))
    if not csv_path.is_absolute():
        csv_path = (cfg.root_dir / csv_path).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"csv not found: {csv_path}")

    timeframe = _as_str(body, "timeframe", cfg.default_timeframe)
    fill_missing = _as_bool(body, "fill_missing", True)

    initial_nav = _as_float(body, "initial_nav", 1_000_000.0)
    aggressiveness = _as_float(body, "aggressiveness", 0.5)

    leverage_cap = _as_float(body, "leverage_cap", 1.5)
    venue_cap_frac = _as_float(body, "venue_cap_frac", 0.30)
    max_drawdown = _as_float(body, "max_drawdown", 0.20)
    liq_buf = _as_float(body, "liquidation_buffer", 0.10)

    fee_bps = _as_float(body, "taker_fee_bps", 5.0)
    slip_bps = _as_float(body, "slippage_bps_at_1x_nav", 10.0)

    frame = _load_frame(csv_path=csv_path, timeframe=timeframe, fill_missing=fill_missing)

    guidance = GuidancePolicy(GuidancePolicyConfig(aggressiveness=aggressiveness))
    risk = RiskGovernor(
        RiskConfig(
            leverage_cap=leverage_cap,
            venue_cap_frac=venue_cap_frac,
            max_drawdown=max_drawdown,
            kill_switch_action="carry_only",
        )
    )
    nav_cfg = RegimeConfig()
    comp_cfg = CompressionConfig()
    sim_cfg = SimulatorConfig(initial_nav=initial_nav, liquidation_buffer=liq_buf)
    fee_model = FeeModel(taker_fee_bps=fee_bps)
    slippage_model = SlippageModel(slippage_bps_at_1x_nav=slip_bps)

    result = simulate_portfolio(
        frame=cast(Any, frame),
        guidance=guidance,
        risk=risk,
        fee_model=fee_model,
        slippage_model=slippage_model,
        nav_config=nav_cfg,
        compression_config=comp_cfg,
        sim_config=sim_cfg,
    )
    metrics = compute_metrics(cast(Any, result))

    shadow_rows: list[dict[str, str]] = []
    if cfg.shadow_path is not None:
        shadow_rows = _read_shadow_csv(cfg.shadow_path)

    return {
        "bars": _serialize_bars(result),
        "trades": _serialize_trades(result),
        "metrics": _serialize_metrics(metrics),
        "shadow": shadow_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Serve the dashboard with a local /api/run endpoint.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--dashboard", type=Path, default=Path("out/dashboard.html"))
    p.add_argument("--shadow", type=Path, default=Path("out/shadow_log.csv"))
    p.add_argument("--csv", type=Path, default=Path("data/hyperliquid_btc_1h.csv"))
    p.add_argument("--timeframe", type=str, default="1h")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path.cwd().resolve()
    dashboard_path = (
        (root / args.dashboard).resolve() if not args.dashboard.is_absolute() else args.dashboard
    )
    shadow_path = (root / args.shadow).resolve() if not args.shadow.is_absolute() else args.shadow
    csv_path = (root / args.csv).resolve() if not args.csv.is_absolute() else args.csv

    cfg = ServeConfig(
        root_dir=root,
        dashboard_path=dashboard_path,
        shadow_path=shadow_path if shadow_path.exists() else None,
        default_csv=csv_path,
        default_timeframe=args.timeframe,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/api/ping", "/api/ping/"):
                _write_json(self, 200, {"ok": True})
                return

            if self.path in ("/", "/index.html"):
                path = cfg.dashboard_path
            else:
                # Serve relative to repo root (allows CSS/images if ever added)
                rel = self.path.lstrip("/").split("?", 1)[0]
                path = (cfg.root_dir / rel).resolve()
                if cfg.root_dir not in path.parents and path != cfg.root_dir:
                    self.send_error(403)
                    return

            if not path.exists() or not path.is_file():
                self.send_error(404)
                return

            mime, _ = mimetypes.guess_type(str(path))
            mime = mime or "application/octet-stream"
            data = path.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                f"{mime}; charset=utf-8" if mime.startswith("text/") else mime,
            )
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in ("/api/run", "/api/run/"):
                self.send_error(404)
                return
            try:
                body = _read_json(self)
                payload = _run_backtest(cfg, body)
                _write_json(self, 200, payload)
            except Exception as e:  # noqa: BLE001
                _write_json(self, 400, {"error": str(e)})

        def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
            # Keep stdout clean; show only server start banner.
            return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"dashboard server: {url}")
    print(f"serving: {cfg.dashboard_path}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
