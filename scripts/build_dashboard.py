#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _build_html(
    *,
    title: str,
    bars: list[dict[str, str]],
    metrics: list[dict[str, str]],
    shadow: list[dict[str, str]],
    trades: list[dict[str, str]],
) -> str:
    payload = {
        "bars": bars,
        "metrics": metrics,
        "shadow": shadow,
        "trades": trades,
        "generated_at_utc": datetime.now(tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    data_json = json.dumps(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      --bg0: #060911;
      --bg1: #0b1020;
      --panel0: #0f1730;
      --panel1: #131f3e;
      --grid: #223259;
      --text: #e8eefc;
      --muted: #9fb0d2;
      --accent: #4dd3ff;
      --green: #4ad48a;
      --red: #ff6b7a;
      --shadow: rgba(0,0,0,0.4);
      --glow: rgba(77,211,255,0.14);
    }}
    body.light {{
      --bg0: #f6f8fc;
      --bg1: #eef3fb;
      --panel0: #ffffff;
      --panel1: #f1f5ff;
      --grid: #d7e1f5;
      --text: #101a2b;
      --muted: #556a91;
      --accent: #0079cc;
      --green: #0f9960;
      --red: #c4455a;
      --shadow: rgba(17,24,39,0.12);
      --glow: rgba(0,121,204,0.10);
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(900px 600px at 78% -18%, #152a55 0%, rgba(21,42,85,0.0) 60%),
        linear-gradient(180deg, var(--bg0), var(--bg1));
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial,
        sans-serif;
    }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 22px; }}
    .top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }}
    .title {{ font-size: 1.55rem; font-weight: 800; letter-spacing: 0.2px; }}
    .sub {{ color: var(--muted); font-size: 0.95rem; }}
    .btn {{
      border: 1px solid var(--grid);
      background: linear-gradient(180deg, var(--panel0), var(--panel1));
      color: var(--text);
      border-radius: 12px;
      padding: 9px 12px;
      cursor: pointer;
      box-shadow: 0 10px 30px var(--shadow);
    }}
    .btn.small {{ padding: 7px 10px; border-radius: 10px; font-size: 0.9rem; }}
    .controls {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      align-items: end;
      margin-top: 8px;
    }}
    .field label {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 0.82rem;
      margin-bottom: 6px;
      font-weight: 700;
    }}
    .field input {{
      width: 100%;
      border: 1px solid var(--grid);
      background: rgba(0,0,0,0.10);
      color: var(--text);
      border-radius: 12px;
      padding: 9px 10px;
      outline: none;
    }}
    body.light .field input {{ background: rgba(255,255,255,0.75); }}
    .cmd {{
      width: 100%;
      min-height: 132px;
      margin-top: 10px;
      border: 1px solid var(--grid);
      background: rgba(0,0,0,0.14);
      color: var(--text);
      border-radius: 12px;
      padding: 10px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
      resize: vertical;
    }}
    body.light .cmd {{ background: rgba(255,255,255,0.8); }}
    .actions {{ display: flex; gap: 10px; margin-top: 10px; align-items: center; }}
    .note {{ color: var(--muted); font-size: 0.86rem; }}
    .prog {{
      margin-top: 10px;
      height: 10px;
      border-radius: 999px;
      border: 1px solid var(--grid);
      background: rgba(0, 0, 0, 0.10);
      overflow: hidden;
      display: none;
    }}
    body.light .prog {{ background: rgba(255,255,255,0.65); }}
    .prog .bar {{
      height: 100%;
      width: 35%;
      background: linear-gradient(90deg, rgba(77,211,255,0.25), rgba(77,211,255,0.95));
      animation: prog 1.1s ease-in-out infinite;
      border-radius: 999px;
    }}
    @keyframes prog {{
      0% {{ transform: translateX(-80%); opacity: 0.65; }}
      50% {{ opacity: 1; }}
      100% {{ transform: translateX(320%); opacity: 0.65; }}
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.86rem;
      font-weight: 650;
    }}
    .swatch {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
      margin-right: 6px;
      border: 1px solid var(--grid);
      vertical-align: middle;
    }}
    .toggle {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      user-select: none;
    }}
    .toggle input {{ cursor: pointer; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 14px;
    }}
    .card {{
      background: linear-gradient(180deg, var(--panel0) 0%, var(--panel1) 100%);
      border: 1px solid var(--grid);
      border-radius: 16px;
      padding: 12px;
      box-shadow: 0 10px 30px var(--shadow);
    }}
    .card.mb {{ margin-bottom: 14px; }}
    .card.hi {{
      box-shadow: 0 10px 30px var(--shadow), 0 0 0 1px rgba(255,255,255,0.02),
        0 0 50px var(--glow);
    }}
    .label {{ color: var(--muted); font-size: 0.82rem; margin-bottom: 6px; }}
    .label-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }}
    .label-row .label {{ margin-bottom: 0; }}
    .info {{
      width: 18px;
      height: 18px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      border: 1px solid var(--grid);
      color: var(--muted);
      font-size: 12px;
      line-height: 1;
      cursor: help;
      user-select: none;
      flex: 0 0 auto;
    }}
    .info:hover {{ color: var(--text); }}
    .value {{ font-size: 1.25rem; font-weight: 800; }}
    .value.small {{ font-size: 1.05rem; }}
    .row {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}
    .section-title {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      font-weight: 800;
      margin-bottom: 8px;
    }}
    .hint {{ color: var(--muted); font-weight: 600; font-size: 0.86rem; }}
    .chart-wrap {{
      position: relative;
      height: 280px;
      border-radius: 14px;
      border: 1px solid var(--grid);
      background: linear-gradient(180deg, rgba(0,0,0,0.10), rgba(0,0,0,0.0));
      overflow: hidden;
    }}
    canvas {{
      width: 100%;
      height: 100%;
      display: block;
    }}
    .tooltip {{
      position: absolute;
      pointer-events: none;
      background: rgba(10, 14, 25, 0.92);
      border: 1px solid var(--grid);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 12px;
      font-size: 0.85rem;
      box-shadow: 0 12px 28px var(--shadow);
      max-width: 280px;
      transform: translate(10px, 10px);
      display: none;
      white-space: pre;
    }}
    body.light .tooltip {{
      background: rgba(255, 255, 255, 0.95);
      color: var(--text);
    }}
    .infotip {{
      position: fixed;
      pointer-events: none;
      background: rgba(10, 14, 25, 0.92);
      border: 1px solid var(--grid);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 12px;
      font-size: 0.85rem;
      box-shadow: 0 12px 28px var(--shadow);
      max-width: 320px;
      display: none;
      z-index: 9999;
      white-space: pre-wrap;
    }}
    body.light .infotip {{
      background: rgba(255, 255, 255, 0.95);
      color: var(--text);
    }}
    .table-wrap {{
      max-height: 280px;
      overflow: auto;
      border-radius: 14px;
      border: 1px solid var(--grid);
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
    th, td {{ text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--grid); }}
    th {{ position: sticky; top: 0; background: var(--panel0); z-index: 2; }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 0.75rem;
      font-weight: 800;
    }}
    .on {{ background: rgba(74,212,138,0.18); color: var(--green); }}
    .off {{ background: rgba(255,107,122,0.18); color: var(--red); }}
    .neutral {{ background: rgba(77,211,255,0.18); color: var(--accent); }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    @media (max-width: 980px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
    @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <div class="title">Trading Research Dashboard</div>
        <div id="subTitle" class="sub">Backtest and shadow-mode outcome viewer</div>
      </div>
      <button id="themeBtn" class="btn">Toggle Theme</button>
    </div>

    <div id="kpis" class="grid"></div>

    <div class="card mb">
      <div class="section-title">
        <div>Rerun Simulation</div>
        <div class="hint">Run button works when served locally</div>
      </div>
      <div class="controls">
        <div class="field">
          <label for="csvPath">
            CSV path
            <span class="info" data-tip="Input OHLCV CSV (UTC timestamps).">i</span>
          </label>
          <input id="csvPath" value="data/hyperliquid_btc_1h.csv" />
        </div>
        <div class="field">
          <label for="timeframe">
            Timeframe
            <span class="info" data-tip="Expected timeframe of the input CSV (e.g. 1h).">i</span>
          </label>
          <input id="timeframe" value="1h" />
        </div>
        <div class="field">
          <label for="initialNav">
            Starting NAV (USD)
            <span class="info" data-tip="Configured starting portfolio equity in USD.">i</span>
          </label>
          <input id="initialNav" value="10,000" />
        </div>
        <div class="field">
          <label for="aggr">
            Guidance aggressiveness (0..1)
            <span
              class="info"
              data-tip="Scales exposure targets within the regime policy bands.
Higher = more aggressive allocation."
            >i</span>
          </label>
          <input id="aggr" value="0.5" />
        </div>
        <div class="field">
          <label for="levCap">
            Portfolio leverage cap
            <span
              class="info"
              data-tip="Internal risk limit: gross exposure / NAV.
This is NOT the exchange maximum leverage."
            >i</span>
          </label>
          <input id="levCap" value="1.5" />
        </div>
        <div class="field">
          <label for="venueCap">
            Venue cap
            <span
              class="info"
              data-tip="Max fraction of NAV allowed to be deployed on this single venue
(carry + directional combined)."
            >i</span>
          </label>
          <input id="venueCap" value="0.30" />
        </div>
        <div class="field">
          <label for="maxDd">
            Max drawdown (0..1)
            <span
              class="info"
              data-tip="Kill-switch threshold:
If (peak NAV - current NAV) / peak NAV exceeds this,
the risk governor switches to carry-only or flat."
            >i</span>
          </label>
          <input id="maxDd" value="0.2" />
        </div>
        <div class="field">
          <label for="liqBuf">
            Liquidation buffer (0..1)
            <span
              class="info"
              data-tip="Safety haircut applied to the leverage cap.
Effective cap = leverage_cap * (1 - buffer).
Proxy for liquidation risk; explicit liquidation price modeling is not implemented yet."
            >i</span>
          </label>
          <input id="liqBuf" value="0.1" />
        </div>
        <div class="field">
          <label for="dirRisk">
            Directional risk budget (target vol)
            <span
              class="info"
              data-tip="Directional sizing knob: target annualized vol for the directional overlay
(lower = smaller directional position). Not a strict 1% stop-loss model."
            >i</span>
          </label>
          <input id="dirRisk" value="0.01" />
        </div>
      </div>
      <div class="actions">
        <button id="runSim" class="btn small">Run Simulation</button>
        <div id="runStatus" class="note"></div>
      </div>
      <div id="runProg" class="prog"><div class="bar"></div></div>
    </div>

    <div class="row">
      <div class="card hi">
        <div class="section-title">
          <div>NAV vs Buy & Hold</div>
          <div class="hint">Wheel zoom, drag pan, hover for tooltip</div>
        </div>
        <div class="chart-wrap">
          <canvas id="navCanvas"></canvas>
          <div id="navTip" class="tooltip mono"></div>
        </div>
        <div class="legend">
          <span>
            <span class="swatch" style="background: rgba(77,211,255,0.95)"></span>
            Strategy NAV
          </span>
          <span>
            <span class="swatch" style="background: rgba(255,255,255,0.65)"></span>
            Buy & hold NAV
          </span>
          <label class="toggle">
            <input id="toggleBH" type="checkbox" checked />
            Show buy & hold
          </label>
          <label class="toggle">
            <input id="toggleTrades" type="checkbox" checked />
            Show trade markers
          </label>
          <label class="toggle">
            <input id="toggleRegime" type="checkbox" checked />
            Show regime changes
          </label>
        </div>
      </div>

      <div class="card">
        <div class="section-title">
          <div>Price (Close)</div>
          <div class="hint">Underlying asset price over time</div>
        </div>
        <div class="chart-wrap">
          <canvas id="pxCanvas"></canvas>
          <div id="pxTip" class="tooltip mono"></div>
        </div>
        <div class="legend">
          <span>
            <span class="swatch" style="background: rgba(255,255,255,0.85)"></span>
            Price
          </span>
          <label class="toggle">
            <input id="toggleDirEntries" type="checkbox" checked />
            Show directional entries
          </label>
        </div>
      </div>

      <div class="card">
        <div class="section-title">
          <div>Leverage</div>
          <div class="hint">Hover shows exact value</div>
        </div>
        <div class="chart-wrap">
          <canvas id="levCanvas"></canvas>
          <div id="levTip" class="tooltip mono"></div>
        </div>
      </div>

      <div class="card">
        <div class="section-title">
          <div>Exposure</div>
          <div class="hint">Carry vs directional (% NAV)</div>
        </div>
        <div class="chart-wrap">
          <canvas id="expCanvas"></canvas>
          <div id="expTip" class="tooltip mono"></div>
        </div>
      </div>

      <div class="card">
        <div class="section-title">
          <div>Shadow Events</div>
          <div class="hint">Most recent rows</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Regime</th>
                <th>Order</th>
                <th>Hypo Fill</th>
                <th>Slip bps</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody id="shadowTable"></tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="section-title">
          <div>Backtest Trades</div>
          <div class="hint">Most recent rows</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Leg</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Notional</th>
                <th>Fee</th>
                <th>Slip</th>
                <th>Bar PnL</th>
              </tr>
            </thead>
            <tbody id="tradeTable"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <div id="infoTip" class="infotip"></div>

  <script>
    const DATA = {data_json};
    let API_BASE = ""; // set by setupRerunControls()

    function toNum(v) {{
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    }}

    function clamp(v, lo, hi) {{
      return Math.max(lo, Math.min(hi, v));
    }}

    function fmt3(v) {{
      const n = Number(v);
      if (!Number.isFinite(n)) return String(v ?? "");
      const abs = Math.abs(n);
      if (abs > 0 && abs < 1e-6) return n.toExponential(3);
      return n.toLocaleString(undefined, {{
        minimumFractionDigits: 3,
        maximumFractionDigits: 3,
      }});
    }}

    function fmt2(v) {{
      const n = Number(v);
      if (!Number.isFinite(n)) return String(v ?? "");
      return n.toLocaleString(undefined, {{
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }});
    }}

    function fmtPct(v) {{
      const n = Number(v);
      if (!Number.isFinite(n)) return String(v ?? "");
      return `${{(n * 100).toFixed(2)}}%`;
    }}

    function parseIso(ts) {{
      const d = new Date(ts);
      return isNaN(d.getTime()) ? null : d;
    }}

    function pad2(x) {{
      return String(x).padStart(2, "0");
    }}

    function fmtDateTime(d) {{
      const dd = pad2(d.getUTCDate());
      const mm = pad2(d.getUTCMonth() + 1);
      const yyyy = d.getUTCFullYear();
      const hh = pad2(d.getUTCHours());
      const min = pad2(d.getUTCMinutes());
      return `${{dd}}/${{mm}}/${{yyyy}} ${{hh}}:${{min}} UTC`;
    }}

    function fmtDate(d) {{
      const dd = pad2(d.getUTCDate());
      const mm = pad2(d.getUTCMonth() + 1);
      const yyyy = d.getUTCFullYear();
      return `${{dd}}/${{mm}}/${{yyyy}}`;
    }}

    function fmtDuration(ms) {{
      const dayMs = 86400 * 1000;
      const days = Math.max(0, Math.floor(ms / dayMs));
      const months = Math.floor(days / 30);
      const remDays = days - months * 30;
      const years = Math.floor(months / 12);
      const remMonths = months - years * 12;
      const parts = [];
      if (years) parts.push(`${{years}}y`);
      if (remMonths) parts.push(`${{remMonths}}mo`);
      if (remDays || !parts.length) parts.push(`${{remDays}}d`);
      return parts.join(" ");
    }}

    function formatTick(date, spanMs) {{
      const y = date.getUTCFullYear();
      const m = pad2(date.getUTCMonth() + 1);
      const d = pad2(date.getUTCDate());
      const hh = pad2(date.getUTCHours());
      const mm = pad2(date.getUTCMinutes());

      if (spanMs >= 1000 * 60 * 60 * 24 * 365 * 2) return String(y);
      if (spanMs >= 1000 * 60 * 60 * 24 * 60) return `${{y}}-${{m}}`;
      if (spanMs >= 1000 * 60 * 60 * 24 * 2) return `${{m}}-${{d}}`;
      if (spanMs >= 1000 * 60 * 60 * 6) return `${{m}}-${{d}} ${{hh}}:00`;
      return `${{hh}}:${{mm}}`;
    }}

    function metricCard(label, value, extra, helpText) {{
      const cls = extra ? "value small" : "value";
      const ex = extra ? `<div class="label">${{extra}}</div>` : "";
      const tip = helpText ? helpText.replaceAll('"', "'") : "";
      const info = helpText ? `<span class="info" data-tip="${{tip}}">i</span>` : "";
      return `<div class="card">
        <div class="label-row"><div class="label">${{label}}</div>${{info}}</div>
        <div class="${{cls}}">${{value}}</div>
        ${{ex}}
      </div>`;
    }}

    function buildKpis(bars, metrics, shadow, trades) {{
      const kpis = [];
      const map = new Map(metrics.map(m => [m.metric, m.value]));

      const initialNavMetric = toNum(map.get("initial_nav"));
      const nav0 = bars.length ? toNum(bars[0].nav) : null;
      const navN = bars.length ? toNum(bars[bars.length - 1].nav) : null;
      const px0 = bars.length ? toNum(bars[0].price) : null;
      const pxN = bars.length ? toNum(bars[bars.length - 1].price) : null;
      const start = bars.length ? bars[0].timestamp : "";
      const end = bars.length ? bars[bars.length - 1].timestamp : "";
      const orderCount = shadow.reduce((acc, r) => {{
        return acc + ((r.intended_order || "").length ? 1 : 0);
      }}, 0);

      const navStart = initialNavMetric != null ? initialNavMetric : nav0;
      const pnl = (navStart != null && navN != null) ? (navN - navStart) : null;
      const ret =
        (navStart != null && navN != null && navStart !== 0) ? ((navN / navStart) - 1) : null;
      const bhNavN =
        (navStart != null && px0 != null && pxN != null && px0 !== 0)
          ? (navStart * (pxN / px0))
          : null;
      const bhRet =
        (navStart != null && bhNavN != null && navStart !== 0) ? ((bhNavN / navStart) - 1) : null;
      const excessRet = (ret != null && bhRet != null) ? (ret - bhRet) : null;

      kpis.push(metricCard(
        "Bars",
        String(bars.length),
        `${{start}} to ${{end}}`,
        "Number of backtest bars. Hover charts for per-bar details."
      ));
      kpis.push(metricCard(
        "Backtest trade events",
        String(trades.length),
        "spot/perp events",
        "Count of trade events emitted by the backtest simulator (spot/perp rebalances). "
          + "This is not the same as round-trip 'trades'."
      ));
      kpis.push(metricCard(
        "Shadow intended orders",
        String(orderCount),
        "intended orders",
        "Count of intended orders produced in shadow mode (skipped rows do not count)."
      ));
      kpis.push(metricCard(
        "Initial NAV",
        navStart == null ? "n/a" : fmt2(navStart),
        "USD",
        "Configured starting portfolio equity (USD)."
      ));
      if (nav0 != null && initialNavMetric != null) {{
        kpis.push(metricCard(
          "NAV after first rebalance",
          fmt2(nav0),
          "USD",
          "The simulator rebalances at the first bar close, "
            + "so fees/slippage may change NAV immediately."
        ));
      }}

      const keys = [
        ["cagr", "CAGR", "Compound annual growth rate from NAV series."],
        ["sharpe", "Sharpe", "Sharpe ratio using per-bar returns (simplified)."],
        ["sortino", "Sortino", "Sortino ratio using downside deviation (simplified)."],
        ["max_drawdown", "Max DD", "Maximum peak-to-trough drawdown on NAV."],
        ["win_rate", "Win rate", "Fraction of bars with positive returns."],
        ["exposure_utilization", "Exposure utilization", "Average gross exposure / NAV."],
        [
          "funding_contribution",
          "Funding contribution",
          "Funding PnL / total PnL. Can be >100% if other components offset it.",
        ],
        [
          "directional_contribution",
          "Directional contribution",
          "Directional overlay PnL / total PnL. Can be >100% if other components offset it.",
        ],
      ];

      for (const [k, label, help] of keys) {{
        if (map.has(k)) {{
          const raw = toNum(map.get(k));
          let shown = raw == null ? "n/a" : fmt3(raw);
          if (k === "cagr" || k === "max_drawdown") shown = raw == null ? "n/a" : fmtPct(raw);
          if (k === "win_rate") shown = raw == null ? "n/a" : fmtPct(raw);
          if (k.endsWith("contribution")) shown = raw == null ? "n/a" : fmtPct(raw);
          kpis.push(metricCard(label, shown, "", help));
        }}
      }}

      if (navN != null) {{
        kpis.push(metricCard(
          "Ending NAV",
          fmt2(navN),
          "USD",
          "Ending portfolio equity (simulated NAV) in USD."
        ));
      }}
      if (pnl != null) {{
        kpis.push(
          metricCard(
            "Total PnL",
            fmt2(pnl),
            "USD",
            "Total PnL = ending NAV - starting NAV (not annualized)."
          )
        );
      }}
      if (ret != null) {{
        kpis.push(
          metricCard(
            "Total return",
            fmtPct(ret),
            "",
            "Total return = ending NAV / starting NAV - 1 (not annualized)."
          )
        );
      }}
      if (bhRet != null) {{
        kpis.push(
          metricCard(
            "Buy & hold return",
            fmtPct(bhRet),
            "",
            "Buy & hold return computed from the underlying close price in the bars export."
          )
        );
      }}
      if (excessRet != null) {{
        kpis.push(
          metricCard(
            "Excess return",
            fmtPct(excessRet),
            "",
            "Excess return = strategy total return - buy & hold return."
          )
        );
      }}
      return kpis.slice(0, 16);
    }}

    function makeChart(canvas, tipEl, series, opts) {{
      const ctx = canvas.getContext("2d");
      let viewStart = 0;
      let viewEnd = Math.max(0, series.length - 1);
      let dragging = false;
      let dragX = 0;
      let dragStart = 0;
      let cssW = 1;
      let cssH = 1;

      function resize() {{
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        cssW = Math.max(1, rect.width);
        cssH = Math.max(1, rect.height);
        canvas.width = Math.max(1, Math.floor(cssW * dpr));
        canvas.height = Math.max(1, Math.floor(cssH * dpr));
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0); // draw in CSS pixels
        draw();
      }}

      function extent() {{
        let min = Infinity;
        let max = -Infinity;
        for (let i = viewStart; i <= viewEnd; i++) {{
          const v = series[i].y;
          if (v == null) continue;
          if (v < min) min = v;
          if (v > max) max = v;
        }}
        if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {{
          min = min === Infinity ? 0 : min - 1;
          max = max === -Infinity ? 1 : max + 1;
        }}
        const pad = (max - min) * 0.08;
        return [min - pad, max + pad];
      }}

      function draw(crossIdx, crossX) {{
        const w = cssW;
        const h = cssH;
        ctx.clearRect(0, 0, w, h);

        const [yMin, yMax] = extent();
        const x0 = 58;
        const y0 = 18;
        const x1 = w - 12;
        const y1 = h - 44;

        ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue("--grid").trim();
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.65;
        for (let k = 0; k <= 4; k++) {{
          const yy = y0 + (k / 4) * (y1 - y0);
          ctx.beginPath();
          ctx.moveTo(x0, yy);
          ctx.lineTo(x1, yy);
          ctx.stroke();
        }}
        ctx.globalAlpha = 1;

        function xFor(i) {{
          const t = (i - viewStart) / Math.max(1, (viewEnd - viewStart));
          return x0 + t * (x1 - x0);
        }}
        function yFor(v) {{
          const t = (v - yMin) / (yMax - yMin);
          return y1 - t * (y1 - y0);
        }}

        const yFmt = opts.yFormat || fmt3;
        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim();
        ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";
        ctx.fillText(yFmt(yMax), 8, y0 + 6);
        ctx.fillText(yFmt(yMin), 8, y1 + 4);

        // Trade markers (dots along the baseline)
        if (opts.markers && opts.markers.length) {{
          for (const idx of opts.markers) {{
            if (idx < viewStart || idx > viewEnd) continue;
            const mx = xFor(idx);
            const meta = series[idx] ? (series[idx].meta || null) : null;
            let pnl = null;
            if (meta) {{
              const p = toNum(meta.pnl_price);
              const f = toNum(meta.pnl_funding);
              const fe = toNum(meta.pnl_fees);
              const sl = toNum(meta.pnl_slippage);
              if (p != null && f != null && fe != null && sl != null) {{
                pnl = p + f + fe + sl;
              }}
            }}
            const isWin = pnl != null ? pnl >= 0 : true;
            ctx.fillStyle = isWin ? "rgba(74,212,138,0.95)" : "rgba(255,107,122,0.95)";
            ctx.beginPath();
            ctx.arc(mx, y1 + 10, 2.2, 0, Math.PI * 2);
            ctx.fill();
          }}
        }}

        // Directional entry markers (triangles at the price line)
        if (opts.dirMarkers && opts.dirMarkers.length) {{
          const spanBars = viewEnd - viewStart;
          const maxSpan = opts.dirMarkerMaxSpan != null ? opts.dirMarkerMaxSpan : 600;
          if (spanBars <= maxSpan) {{
            for (const m of opts.dirMarkers) {{
              const idx = m.idx;
              if (idx < viewStart || idx > viewEnd) continue;
              const row = series[idx];
              if (!row || row.y == null) continue;
              const mx = xFor(idx);
              const my = yFor(row.y);
              const up = m.side === "long";
              ctx.fillStyle = up ? "rgba(74,212,138,0.95)" : "rgba(255,107,122,0.95)";
              ctx.beginPath();
              if (up) {{
                ctx.moveTo(mx, my - 8);
                ctx.lineTo(mx - 6, my + 4);
                ctx.lineTo(mx + 6, my + 4);
              }} else {{
                ctx.moveTo(mx, my + 8);
                ctx.lineTo(mx - 6, my - 4);
                ctx.lineTo(mx + 6, my - 4);
              }}
              ctx.closePath();
              ctx.fill();
            }}
          }}
        }}

        let started = false;
        let firstX = null;
        let lastX = null;
        ctx.beginPath();
        for (let i = viewStart; i <= viewEnd; i++) {{
          const v = series[i].y;
          if (v == null) {{
            started = false;
            continue;
          }}
          const xx = xFor(i);
          const yy = yFor(v);
          if (!started) {{
            ctx.moveTo(xx, yy);
            firstX = xx;
            started = true;
          }} else {{
            ctx.lineTo(xx, yy);
          }}
          lastX = xx;
        }}
        if (opts.fill && firstX != null && lastX != null) {{
          const grad = ctx.createLinearGradient(0, y0, 0, y1);
          const top = opts.fillTop || "rgba(77,211,255,0.25)";
          const bot = opts.fillBottom || "rgba(77,211,255,0.0)";
          grad.addColorStop(0, top);
          grad.addColorStop(1, bot);
          ctx.save();
          ctx.fillStyle = grad;
          ctx.lineTo(lastX, y1);
          ctx.lineTo(firstX, y1);
          ctx.closePath();
          ctx.fill();
          ctx.restore();
        }}
        ctx.strokeStyle = opts.color;
        ctx.lineWidth = 2.2;
        ctx.stroke();

        // Regime change dots (uses series[i].meta.regime when available).
        if (opts.showRegimeDots) {{
          let prev = null;
          for (let i = viewStart; i <= viewEnd; i++) {{
            const m = series[i].meta || null;
            const r = m ? (m.regime || null) : null;
            if (r == null) continue;
            if (r !== prev) {{
              const xx = xFor(i);
              const yy = y1 + 10;
              let col = "rgba(77,211,255,0.9)";
              if (r === "RISK_ON") col = "rgba(74,212,138,0.95)";
              if (r === "RISK_OFF") col = "rgba(255,107,122,0.95)";
              ctx.fillStyle = col;
              ctx.beginPath();
              ctx.arc(xx, yy, 2.4, 0, Math.PI * 2);
              ctx.fill();
              prev = r;
            }}
          }}
        }}

        if (crossIdx != null) {{
          const row = series[crossIdx];
          if (row && row.y != null) {{
            const cx = crossX != null ? crossX : xFor(crossIdx);
            const cy = yFor(row.y);
            ctx.strokeStyle = "rgba(255,255,255,0.25)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(cx, y0);
            ctx.lineTo(cx, y1);
            ctx.stroke();

            ctx.fillStyle = opts.color;
            ctx.beginPath();
            ctx.arc(cx, cy, 3.6, 0, Math.PI * 2);
            ctx.fill();
          }}
        }}

        // X labels
        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim();
        ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";
        if (series.length) {{
          const d0 = parseIso(series[viewStart].t || "");
          const d1 = parseIso(series[viewEnd].t || "");
          const spanMs = (d0 && d1) ? Math.max(1, d1.getTime() - d0.getTime()) : 1;
          for (let k = 0; k <= 4; k++) {{
            const idx = Math.round(viewStart + (k / 4) * (viewEnd - viewStart));
            const dt = parseIso(series[idx].t || "");
            if (!dt) continue;
            const label = formatTick(dt, spanMs);
            const xx = xFor(idx);
            const wLab = ctx.measureText(label).width;
            ctx.fillText(label, clamp(xx - wLab / 2, x0, x1 - wLab), h - 18);
          }}
        }}

        // Axis labels
        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim();
        ctx.font = "12px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif";
        const xLabel = opts.xLabel || "";
        if (xLabel) {{
          const wLab = ctx.measureText(xLabel).width;
          ctx.fillText(xLabel, clamp((x0 + x1) / 2 - wLab / 2, x0, x1 - wLab), h - 6);
        }}
        const yLabel = opts.yLabel || "";
        if (yLabel) {{
          ctx.save();
          ctx.translate(16, (y0 + y1) / 2);
          ctx.rotate(-Math.PI / 2);
          const wy = ctx.measureText(yLabel).width;
          ctx.fillText(yLabel, -wy / 2, 0);
          ctx.restore();
        }}
      }}

      function idxAt(clientX) {{
        const rect = canvas.getBoundingClientRect();
        const w = rect.width;
        const x0 = 58;
        const x1 = w - 12;
        const x = Math.max(x0, Math.min(x1, clientX - rect.left));
        const t = (x - x0) / Math.max(1, (x1 - x0));
        const i = Math.round(viewStart + t * (viewEnd - viewStart));
        return [Math.max(viewStart, Math.min(viewEnd, i)), x];
      }}

      canvas.addEventListener("mousemove", (e) => {{
        const [i, x] = idxAt(e.clientX);
        const row = series[i];
        if (!row) return;
        tipEl.style.display = "block";
        tipEl.style.left = `${{e.offsetX}}px`;
        tipEl.style.top = `${{e.offsetY}}px`;
        if (opts.tooltip) {{
          tipEl.textContent = opts.tooltip(row);
        }} else {{
          tipEl.textContent = `${{row.t}}\\n${{opts.label}}=${{fmt3(row.y)}}`;
        }}
        draw(i, x);
      }});
      canvas.addEventListener("mouseleave", () => {{
        tipEl.style.display = "none";
        draw();
      }});

      canvas.addEventListener("wheel", (e) => {{
        e.preventDefault();
        if (series.length < 2) return;
        const [i] = idxAt(e.clientX);
        const span = Math.max(5, viewEnd - viewStart);

        const wantPan = e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY);
        if (wantPan) {{
          const delta = (Math.abs(e.deltaX) > 0) ? e.deltaX : e.deltaY;
          const rect = canvas.getBoundingClientRect();
          const frac = delta / Math.max(1, rect.width);
          const shift = Math.round(frac * span);
          let ns = viewStart + shift;
          let ne = viewEnd + shift;
          if (ns < 0) {{ ne -= ns; ns = 0; }}
          if (ne > series.length - 1) {{
            ns -= (ne - (series.length - 1));
            ne = series.length - 1;
          }}
          viewStart = Math.max(0, ns);
          viewEnd = Math.max(viewStart, Math.min(series.length - 1, ne));
          draw();
          return;
        }}

        const zoom = e.deltaY < 0 ? 0.75 : 1.33;
        let newSpan = Math.max(5, Math.floor(span * zoom));
        newSpan = Math.min(series.length - 1, newSpan);
        let ns = i - Math.floor(newSpan / 2);
        let ne = ns + newSpan;
        if (ns < 0) {{ ne -= ns; ns = 0; }}
        if (ne > series.length - 1) {{
          ns -= (ne - (series.length - 1));
          ne = series.length - 1;
        }}
        viewStart = Math.max(0, ns);
        viewEnd = Math.max(viewStart, Math.min(series.length - 1, ne));
        draw();
      }}, {{ passive: false }});

      canvas.addEventListener("mousedown", (e) => {{
        dragging = true;
        dragX = e.clientX;
        dragStart = viewStart;
      }});
      canvas.addEventListener("dblclick", () => {{
        viewStart = 0;
        viewEnd = Math.max(0, series.length - 1);
        draw();
      }});
      window.addEventListener("mouseup", () => {{ dragging = false; }});
      window.addEventListener("mousemove", (e) => {{
        if (!dragging) return;
        const rect = canvas.getBoundingClientRect();
        const px = e.clientX - dragX;
        const frac = px / Math.max(1, rect.width);
        const span = viewEnd - viewStart;
        const shift = Math.round(-frac * span);
        let ns = dragStart + shift;
        let ne = ns + span;
        if (ns < 0) {{ ne -= ns; ns = 0; }}
        if (ne > series.length - 1) {{ ns -= (ne - (series.length - 1)); ne = series.length - 1; }}
        viewStart = Math.max(0, ns);
        viewEnd = Math.max(viewStart, Math.min(series.length - 1, ne));
        draw();
      }});

      window.addEventListener("resize", resize);
      resize();
      return {{ resize }};
    }}

    function makeMultiChart(canvas, tipEl, seriesList, opts) {{
      const ctx = canvas.getContext("2d");
      let viewStart = 0;
      let viewEnd = Math.max(0, seriesList[0].length - 1);
      let cssW = 1;
      let cssH = 1;

      function resize() {{
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        cssW = Math.max(1, rect.width);
        cssH = Math.max(1, rect.height);
        canvas.width = Math.max(1, Math.floor(cssW * dpr));
        canvas.height = Math.max(1, Math.floor(cssH * dpr));
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        draw();
      }}

      function extent() {{
        let min = Infinity;
        let max = -Infinity;
        for (const s of seriesList) {{
          for (let i = viewStart; i <= viewEnd; i++) {{
            const v = s[i].y;
            if (v == null) continue;
            if (v < min) min = v;
            if (v > max) max = v;
          }}
        }}
        if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {{
          min = min === Infinity ? 0 : min - 1;
          max = max === -Infinity ? 1 : max + 1;
        }}
        const pad = (max - min) * 0.08;
        return [min - pad, max + pad];
      }}

      function draw(crossIdx, crossX) {{
        const w = cssW;
        const h = cssH;
        ctx.clearRect(0, 0, w, h);

        const [yMin, yMax] = extent();
        const x0 = 58;
        const y0 = 18;
        const x1 = w - 12;
        const y1 = h - 44;

        ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue("--grid").trim();
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.65;
        for (let k = 0; k <= 4; k++) {{
          const yy = y0 + (k / 4) * (y1 - y0);
          ctx.beginPath();
          ctx.moveTo(x0, yy);
          ctx.lineTo(x1, yy);
          ctx.stroke();
        }}
        ctx.globalAlpha = 1;

        function xFor(i) {{
          const t = (i - viewStart) / Math.max(1, (viewEnd - viewStart));
          return x0 + t * (x1 - x0);
        }}
        function yFor(v) {{
          const t = (v - yMin) / (yMax - yMin);
          return y1 - t * (y1 - y0);
        }}

        const yFmt = opts.yFormat || fmt3;
        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim();
        ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";
        ctx.fillText(yFmt(yMax), 8, y0 + 6);
        ctx.fillText(yFmt(yMin), 8, y1 + 4);

        // Trade markers and regime change dots use seriesList[0].meta when available.
        if (opts.markers && opts.markers.length) {{
          for (const idx of opts.markers) {{
            if (idx < viewStart || idx > viewEnd) continue;
            const mx = xFor(idx);
            const meta = seriesList[0][idx] ? (seriesList[0][idx].meta || null) : null;
            let pnl = null;
            if (meta) {{
              const p = toNum(meta.pnl_price);
              const f = toNum(meta.pnl_funding);
              const fe = toNum(meta.pnl_fees);
              const sl = toNum(meta.pnl_slippage);
              if (p != null && f != null && fe != null && sl != null) {{
                pnl = p + f + fe + sl;
              }}
            }}
            const isWin = pnl != null ? pnl >= 0 : true;
            ctx.fillStyle = isWin ? "rgba(74,212,138,0.95)" : "rgba(255,107,122,0.95)";
            ctx.beginPath();
            ctx.arc(mx, y1 + 10, 2.2, 0, Math.PI * 2);
            ctx.fill();
          }}
        }}

        if (opts.showRegimeDots) {{
          let prev = null;
          for (let i = viewStart; i <= viewEnd; i++) {{
            const m = seriesList[0][i].meta || null;
            const r = m ? (m.regime || null) : null;
            if (r == null) continue;
            if (r !== prev) {{
              const xx = xFor(i);
              const yy = y1 + 10;
              let col = "rgba(77,211,255,0.9)";
              if (r === "RISK_ON") col = "rgba(74,212,138,0.95)";
              if (r === "RISK_OFF") col = "rgba(255,107,122,0.95)";
              ctx.fillStyle = col;
              ctx.beginPath();
              ctx.arc(xx, yy, 2.4, 0, Math.PI * 2);
              ctx.fill();
              prev = r;
            }}
          }}
        }}

        for (let si = 0; si < seriesList.length; si++) {{
          const s = seriesList[si];
          let started = false;
          let firstX = null;
          let lastX = null;
          ctx.beginPath();
          for (let i = viewStart; i <= viewEnd; i++) {{
            const v = s[i].y;
            if (v == null) {{
              started = false;
              continue;
            }}
            const xx = xFor(i);
            const yy = yFor(v);
            if (!started) {{
              ctx.moveTo(xx, yy);
              firstX = xx;
              started = true;
            }} else {{
              ctx.lineTo(xx, yy);
            }}
            lastX = xx;
          }}
          if (opts.fillIndex === si && firstX != null && lastX != null) {{
            const grad = ctx.createLinearGradient(0, y0, 0, y1);
            const top = opts.fillTop || "rgba(77,211,255,0.25)";
            const bot = opts.fillBottom || "rgba(77,211,255,0.0)";
            grad.addColorStop(0, top);
            grad.addColorStop(1, bot);
            ctx.save();
            ctx.fillStyle = grad;
            ctx.lineTo(lastX, y1);
            ctx.lineTo(firstX, y1);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
          }}
          ctx.strokeStyle = opts.colors[si];
          ctx.lineWidth = 2.0;
          ctx.stroke();
        }}

        if (crossIdx != null) {{
          const cx = crossX != null ? crossX : xFor(crossIdx);
          ctx.strokeStyle = "rgba(255,255,255,0.25)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(cx, y0);
          ctx.lineTo(cx, y1);
          ctx.stroke();
        }}

        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim();
        ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";
        if (seriesList[0].length) {{
          const d0 = parseIso(seriesList[0][viewStart].t || "");
          const d1 = parseIso(seriesList[0][viewEnd].t || "");
          const spanMs = (d0 && d1) ? Math.max(1, d1.getTime() - d0.getTime()) : 1;
          for (let k = 0; k <= 4; k++) {{
            const idx = Math.round(viewStart + (k / 4) * (viewEnd - viewStart));
            const dt = parseIso(seriesList[0][idx].t || "");
            if (!dt) continue;
            const label = formatTick(dt, spanMs);
            const xx = xFor(idx);
            const wLab = ctx.measureText(label).width;
            ctx.fillText(label, clamp(xx - wLab / 2, x0, x1 - wLab), h - 18);
          }}
        }}

        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim();
        ctx.font = "12px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif";
        const xLabel = opts.xLabel || "";
        if (xLabel) {{
          const wLab = ctx.measureText(xLabel).width;
          ctx.fillText(xLabel, clamp((x0 + x1) / 2 - wLab / 2, x0, x1 - wLab), h - 6);
        }}
        const yLabel = opts.yLabel || "";
        if (yLabel) {{
          ctx.save();
          ctx.translate(16, (y0 + y1) / 2);
          ctx.rotate(-Math.PI / 2);
          const wy = ctx.measureText(yLabel).width;
          ctx.fillText(yLabel, -wy / 2, 0);
          ctx.restore();
        }}
      }}

      function idxAt(clientX) {{
        const rect = canvas.getBoundingClientRect();
        const w = rect.width;
        const x0 = 58;
        const x1 = w - 12;
        const x = Math.max(x0, Math.min(x1, clientX - rect.left));
        const t = (x - x0) / Math.max(1, (x1 - x0));
        const i = Math.round(viewStart + t * (viewEnd - viewStart));
        return [Math.max(viewStart, Math.min(viewEnd, i)), x];
      }}

      canvas.addEventListener("mousemove", (e) => {{
        const [i, x] = idxAt(e.clientX);
        const t = seriesList[0][i] ? seriesList[0][i].t : "";
        const vals = seriesList.map(s => s[i].y);
        tipEl.style.display = "block";
        tipEl.style.left = `${{e.offsetX}}px`;
        tipEl.style.top = `${{e.offsetY}}px`;
        tipEl.textContent = opts.tooltip(t, vals);
        draw(i, x);
      }});
      canvas.addEventListener("mouseleave", () => {{
        tipEl.style.display = "none";
        draw();
      }});

      canvas.addEventListener("wheel", (e) => {{
        e.preventDefault();
        if (seriesList[0].length < 2) return;
        const [i] = idxAt(e.clientX);
        const span = Math.max(5, viewEnd - viewStart);

        const wantPan = e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY);
        if (wantPan) {{
          const delta = (Math.abs(e.deltaX) > 0) ? e.deltaX : e.deltaY;
          const rect = canvas.getBoundingClientRect();
          const frac = delta / Math.max(1, rect.width);
          const shift = Math.round(frac * span);
          let ns = viewStart + shift;
          let ne = viewEnd + shift;
          if (ns < 0) {{ ne -= ns; ns = 0; }}
          if (ne > seriesList[0].length - 1) {{
            ns -= (ne - (seriesList[0].length - 1));
            ne = seriesList[0].length - 1;
          }}
          viewStart = Math.max(0, ns);
          viewEnd = Math.max(viewStart, Math.min(seriesList[0].length - 1, ne));
          draw();
          return;
        }}

        const zoom = e.deltaY < 0 ? 0.75 : 1.33;
        let newSpan = Math.max(5, Math.floor(span * zoom));
        newSpan = Math.min(seriesList[0].length - 1, newSpan);
        let ns = i - Math.floor(newSpan / 2);
        let ne = ns + newSpan;
        if (ns < 0) {{ ne -= ns; ns = 0; }}
        if (ne > seriesList[0].length - 1) {{
          ns -= (ne - (seriesList[0].length - 1));
          ne = seriesList[0].length - 1;
        }}
        viewStart = Math.max(0, ns);
        viewEnd = Math.max(viewStart, Math.min(seriesList[0].length - 1, ne));
        draw();
      }}, {{ passive: false }});

      canvas.addEventListener("dblclick", () => {{
        viewStart = 0;
        viewEnd = Math.max(0, seriesList[0].length - 1);
        draw();
      }});

      window.addEventListener("resize", resize);
      resize();
      return {{ resize }};
    }}

    function renderTables(shadow, trades, barPnlByTs) {{
      const body = document.getElementById("shadowTable");
      const rows = shadow.slice(-250);
      body.innerHTML = rows.map(r => {{
        const regime = r.regime || "";
        const cls = regime === "RISK_ON" ? "on" : (regime === "RISK_OFF" ? "off" : "neutral");
        return `<tr>
          <td class="mono">${{r.timestamp || ""}}</td>
          <td><span class="pill ${{cls}}">${{regime}}</span></td>
          <td class="mono">${{r.intended_order || ""}}</td>
          <td class="mono">${{r.hypothetical_fill || ""}}</td>
          <td class="mono">${{fmt3(r.slippage_estimate_bps || "")}}</td>
          <td class="mono">${{r.reason || ""}}</td>
        </tr>`;
      }}).join("");

      const tBody = document.getElementById("tradeTable");
      const tRows = trades.slice(-250);
      tBody.innerHTML = tRows.map(r => {{
        const qty = toNum(r.qty_delta || r.qty);
        const side = qty == null ? "" : (qty >= 0 ? "BUY" : "SELL");
        const sideCls = qty == null ? "neutral" : (qty >= 0 ? "on" : "off");
        const ts = r.ts || r.timestamp || "";
        const barPnl = (barPnlByTs && ts) ? barPnlByTs.get(ts) : null;
        const barCls = (barPnl != null && barPnl < 0) ? "off" : "on";
        return `<tr>
          <td class="mono">${{ts}}</td>
          <td class="mono">${{r.leg || ""}}</td>
          <td><span class="pill ${{sideCls}}">${{side}}</span></td>
          <td class="mono">${{fmt3(r.qty_delta || r.qty || "")}}</td>
          <td class="mono">${{fmt3(r.price || "")}}</td>
          <td class="mono">${{fmt3(r.notional || "")}}</td>
          <td class="mono">${{fmt3(r.fee || "")}}</td>
          <td class="mono">${{fmt3(r.slippage || "")}}</td>
          <td><span class="pill ${{barCls}}">${{barPnl == null ? "" : fmt2(barPnl)}}</span></td>
        </tr>`;
      }}).join("");
    }}

    function resetCanvas(id) {{
      const old = document.getElementById(id);
      if (!old || !old.parentNode) return old;
      const c = document.createElement("canvas");
      c.id = id;
      old.parentNode.replaceChild(c, old);
      return c;
    }}

    function renderDashboard(payload) {{
      const bars = payload.bars || [];
      const metrics = payload.metrics || [];
      const shadow = payload.shadow || [];
      const trades = payload.trades || [];
      const gen = payload.generated_at_utc || "";

      const kpis = buildKpis(bars, metrics, shadow, trades);
      document.getElementById("kpis").innerHTML = kpis.join("");

      const start = bars.length ? bars[0].timestamp : "";
      const end = bars.length ? bars[bars.length - 1].timestamp : "";
      const subEl = document.getElementById("subTitle");
      if (subEl) {{
        const sdt = parseIso(start);
        const edt = parseIso(end);
        const dur = (sdt && edt) ? fmtDuration(edt.getTime() - sdt.getTime()) : "";
        const sTxt = sdt ? fmtDate(sdt) : start;
        const eTxt = edt ? fmtDate(edt) : end;
        const span = dur ? (" (" + dur + ")") : "";
        subEl.textContent = `Data ${{sTxt}} → ${{eTxt}}${{span}}`;
      }}

      const tsToIdx = new Map();
      for (let i = 0; i < bars.length; i++) {{
        tsToIdx.set(bars[i].timestamp, i);
      }}
      const tradeMarkers = [];
      for (const t of trades) {{
        const key = t.ts || t.timestamp;
        const idx = tsToIdx.get(key);
        if (idx != null) tradeMarkers.push(idx);
      }}

      const navSeries = bars.map(b => ({{
        t: b.timestamp,
        y: toNum(b.nav),
        meta: b,
      }}));
      const pxSeries = bars.map(b => ({{
        t: b.timestamp,
        y: toNum(b.price),
        meta: b,
      }}));
      const levSeries = bars.map(b => ({{
        t: b.timestamp,
        y: toNum(b.leverage),
        meta: b,
      }}));

      const metricMap = new Map(metrics.map(m => [m.metric, m.value]));
      const initialNavMetric = toNum(metricMap.get("initial_nav"));

      const nav0 = navSeries.length ? navSeries[0].y : null;
      const px0 = pxSeries.length ? pxSeries[0].y : null;
      const navStart = initialNavMetric != null ? initialNavMetric : nav0;
      const bhSeries = bars.map((b, i) => {{
        const px = pxSeries[i].y;
        let bh = null;
        if (navStart != null && px0 != null && px != null && px0 !== 0) {{
          bh = navStart * (px / px0);
        }}
        return {{
          t: b.timestamp,
          y: bh,
          meta: b,
        }};
      }});

      const barPnlByTs = new Map();
      for (const b of bars) {{
        const p = toNum(b.pnl_price) ?? 0;
        const f = toNum(b.pnl_funding) ?? 0;
        const fe = toNum(b.pnl_fees) ?? 0;
        const sl = toNum(b.pnl_slippage) ?? 0;
        barPnlByTs.set(b.timestamp, p + f + fe + sl);
      }}

      const carryPct = bars.map(b => ({{
        t: b.timestamp,
        y: (toNum(b.carry_notional) != null && toNum(b.nav) != null && toNum(b.nav) !== 0)
          ? (toNum(b.carry_notional) / toNum(b.nav))
          : null,
        meta: b,
      }}));
      const dirPct = bars.map(b => ({{
        t: b.timestamp,
        y: (toNum(b.directional_notional) != null && toNum(b.nav) != null && toNum(b.nav) !== 0)
          ? (toNum(b.directional_notional) / toNum(b.nav))
          : null,
        meta: b,
      }}));

      const navCanvas = resetCanvas("navCanvas");
      const pxCanvas = resetCanvas("pxCanvas");
      const levCanvas = resetCanvas("levCanvas");
      const expCanvas = resetCanvas("expCanvas");

      const showBH = (document.getElementById("toggleBH")?.checked ?? true);
      const showTrades = (document.getElementById("toggleTrades")?.checked ?? true);
      const showRegime = (document.getElementById("toggleRegime")?.checked ?? true);
      const showDirEntries = (document.getElementById("toggleDirEntries")?.checked ?? true);

      if (showBH) {{
        makeMultiChart(
          navCanvas,
          document.getElementById("navTip"),
          [navSeries, bhSeries],
          {{
            colors: ["rgba(77,211,255,0.95)", "rgba(255,255,255,0.65)"],
            fillIndex: 0,
            fillTop: "rgba(77,211,255,0.28)",
            fillBottom: "rgba(77,211,255,0.0)",
            xLabel: "Date",
            yLabel: "NAV (USD)",
            yFormat: fmt2,
            markers: showTrades ? tradeMarkers : [],
            showRegimeDots: showRegime,
            tooltip: (t, vals) => {{
              const nav = vals[0];
              const bh = vals[1];
              const idx = tsToIdx.get(t);
              const m = (idx != null) ? bars[idx] : {{}};
              const carryNotional = toNum(m.carry_notional);
              const dirNotional = toNum(m.directional_notional);
              const pnl =
                (toNum(m.pnl_price) ?? 0) +
                (toNum(m.pnl_funding) ?? 0) +
                (toNum(m.pnl_fees) ?? 0) +
                (toNum(m.pnl_slippage) ?? 0);
              const carryP =
                (carryNotional != null && nav != null && nav !== 0)
                  ? (carryNotional / nav)
                  : null;
              const dirP =
                (dirNotional != null && nav != null && nav !== 0) ? (dirNotional / nav) : null;
              const dirDir = (dirNotional ?? 0) >= 0 ? "LONG" : "SHORT";
              const carryLine =
                `Carry=${{fmt2(carryNotional)}} USD ` +
                `(${{carryP == null ? "n/a" : fmtPct(carryP)}}) ` +
                "(spot long / perp short)";
              const dirLine =
                `Directional=${{fmt2(dirNotional)}} USD ` +
                `(${{dirP == null ? "n/a" : fmtPct(dirP)}}) ` +
                `(${{dirDir}} perp)`;
              const rel = (nav != null && bh != null && bh !== 0) ? ((nav / bh) - 1) : null;
              return [
                t,
                `Strategy NAV=${{nav == null ? "n/a" : fmt2(nav)}} USD`,
                `Buy&Hold NAV=${{bh == null ? "n/a" : fmt2(bh)}} USD`,
                `Strategy vs B&H=${{rel == null ? "n/a" : fmtPct(rel)}}`,
                `Price=${{fmt2(toNum(m.price) ?? 0)}}`,
                `Leverage=${{fmt3(m.leverage)}}`,
                `Regime=${{m.regime || ""}}`,
                carryLine,
                dirLine,
                `Gross exposure=${{fmt2(m.gross_exposure)}} USD`,
                `Bar PnL=${{fmt2(pnl)}} USD`,
                `Funding PnL=${{fmt2(m.pnl_funding)}} USD`,
                `Fees=${{fmt2(m.pnl_fees)}} USD`,
                `Slippage=${{fmt2(m.pnl_slippage)}} USD`,
                `Kill switch=${{m.kill_switch_active}}`,
              ].join("\\n");
            }},
          }}
        );
      }} else {{
        makeChart(
          navCanvas,
          document.getElementById("navTip"),
          navSeries,
          {{
            color: "rgba(77,211,255,0.95)",
            fill: true,
            fillTop: "rgba(77,211,255,0.28)",
            fillBottom: "rgba(77,211,255,0.0)",
            xLabel: "Date",
            yLabel: "NAV (USD)",
            yFormat: fmt2,
            label: "nav",
            markers: showTrades ? tradeMarkers : [],
            showRegimeDots: showRegime,
          }},
        );
      }}

      // Directional entries: mark transitions from ~0 -> non-zero and sign changes.
      const dirMarkers = [];
      for (let i = 1; i < bars.length; i++) {{
        const prev = toNum(bars[i - 1].directional_notional) ?? 0;
        const cur = toNum(bars[i].directional_notional) ?? 0;
        const eps = 1e-9;
        if (Math.abs(prev) <= eps && Math.abs(cur) > eps) {{
          dirMarkers.push({{ idx: i, side: cur >= 0 ? "long" : "short" }});
        }} else if (Math.abs(prev) > eps && Math.abs(cur) > eps && (prev > 0) !== (cur > 0)) {{
          dirMarkers.push({{ idx: i, side: cur >= 0 ? "long" : "short" }});
        }}
      }}

      makeChart(
        pxCanvas,
        document.getElementById("pxTip"),
        pxSeries,
        {{
          color: "rgba(255,255,255,0.85)",
          xLabel: "Date",
          yLabel: "Price (USD)",
          yFormat: fmt2,
          label: "price",
          markers: showTrades ? tradeMarkers : [],
          showRegimeDots: showRegime,
          dirMarkers: (showDirEntries ? dirMarkers : []),
          dirMarkerMaxSpan: 800,
          tooltip: (row) => {{
            const m = row.meta || {{}};
            const dn = toNum(m.directional_notional) ?? 0;
            return [
              row.t,
              `Price=${{fmt2(toNum(m.price) ?? 0)}}`,
              `Regime=${{m.regime || ""}}`,
              `Directional notional=${{fmt2(dn)}} USD`,
            ].join("\\n");
          }},
        }}
      );

      // Toggle re-render.
      const toggleIds = ["toggleBH", "toggleTrades", "toggleRegime", "toggleDirEntries"];
      for (const id of toggleIds) {{
        const el = document.getElementById(id);
        if (el && !el.__wired) {{
          el.addEventListener("change", () => renderDashboard(payload));
          el.__wired = true;
        }}
      }}

      makeChart(
        levCanvas,
        document.getElementById("levTip"),
        levSeries,
        {{
          color: "rgba(74,212,138,0.95)",
          xLabel: "Date",
          yLabel: "Leverage",
          yFormat: fmt3,
          label: "leverage",
          markers: showTrades ? tradeMarkers : [],
          tooltip: (row) => {{
            const m = row.meta || {{}};
            return [
              row.t,
              `Leverage=${{fmt3(m.leverage)}}`,
              `Gross exposure=${{fmt2(m.gross_exposure)}} USD`,
              `NAV=${{fmt2(m.nav)}} USD`,
              `Regime=${{m.regime || ""}}`,
            ].join("\\n");
          }},
        }}
      );

      makeMultiChart(
        expCanvas,
        document.getElementById("expTip"),
        [carryPct, dirPct],
        {{
          colors: ["rgba(77,211,255,0.95)", "rgba(255,215,109,0.95)"],
          xLabel: "Date",
          yLabel: "% NAV",
          yFormat: fmtPct,
          tooltip: (t, vals) => {{
            const c = vals[0];
            const d = vals[1];
            return [
              t,
              `Carry=${{c == null ? "n/a" : fmtPct(c)}} (spot long / perp short)`,
              `Directional=${{d == null ? "n/a" : fmtPct(d)}} (perp; sign shows long/short)`,
            ].join(\"\\n\");
          }},
        }}
      );

      renderTables(shadow, trades, barPnlByTs);
      return;

      makeMultiChart(
        navCanvas,
        document.getElementById("navTip"),
        [navSeries, bhSeries],
        {{
          colors: ["rgba(77,211,255,0.95)", "rgba(255,255,255,0.65)"],
          markers: tradeMarkers,
          showRegimeDots: true,
          tooltip: (t, vals) => {{
            const nav = vals[0];
            const bh = vals[1];
            const idx = tsToIdx.get(t);
            const m = (idx != null) ? bars[idx] : {{}};
            const carryNotional = toNum(m.carry_notional);
            const dirNotional = toNum(m.directional_notional);
            const pnl =
              (toNum(m.pnl_price) ?? 0) +
              (toNum(m.pnl_funding) ?? 0) +
              (toNum(m.pnl_fees) ?? 0) +
              (toNum(m.pnl_slippage) ?? 0);
            const carryP =
              (carryNotional != null && nav != null && nav !== 0)
                ? (carryNotional / nav)
                : null;
            const dirP =
              (dirNotional != null && nav != null && nav !== 0) ? (dirNotional / nav) : null;
            const dirDir = (dirNotional ?? 0) >= 0 ? "LONG" : "SHORT";
            const carryLine =
              `Carry=${{fmt2(carryNotional)}} USD ` +
              `(${{carryP == null ? "n/a" : fmtPct(carryP)}}) ` +
              "(spot long / perp short)";
            const dirLine =
              `Directional=${{fmt2(dirNotional)}} USD ` +
              `(${{dirP == null ? "n/a" : fmtPct(dirP)}}) ` +
              `(${{dirDir}} perp)`;
            const rel = (nav != null && bh != null && bh !== 0) ? ((nav / bh) - 1) : null;
            return [
              t,
              `Strategy NAV=${{nav == null ? "n/a" : fmt2(nav)}} USD`,
              `Buy&Hold NAV=${{bh == null ? "n/a" : fmt2(bh)}} USD`,
              `Strategy vs B&H=${{rel == null ? "n/a" : fmtPct(rel)}}`,
              `Price=${{fmt2(toNum(m.price) ?? 0)}}`,
              `Leverage=${{fmt3(m.leverage)}}`,
              `Regime=${{m.regime || ""}}`,
              carryLine,
              dirLine,
              `Gross exposure=${{fmt2(m.gross_exposure)}} USD`,
              `Bar PnL=${{fmt2(pnl)}} USD`,
              `Funding PnL=${{fmt2(m.pnl_funding)}} USD`,
              `Fees=${{fmt2(m.pnl_fees)}} USD`,
              `Slippage=${{fmt2(m.pnl_slippage)}} USD`,
              `Kill switch=${{m.kill_switch_active}}`,
            ].join("\\n");
          }},
        }}
      );
    }}

    function main() {{
      renderDashboard(DATA);
    }}

    function _readInputStr(id, fallback) {{
      const el = document.getElementById(id);
      if (!el) return fallback;
      const s = String(el.value || "").trim();
      return s.length ? s : fallback;
    }}

    function setupInfoTips() {{
      const tip = document.getElementById("infoTip");
      if (!tip) return;

      function showFor(el, clientX, clientY) {{
        const txt = (el && el.dataset) ? (el.dataset.tip || "") : "";
        if (!txt) return;
        tip.textContent = txt;
        tip.style.display = "block";
        tip.style.left = `${{clientX + 12}}px`;
        tip.style.top = `${{clientY + 12}}px`;
      }}

      function hide() {{
        tip.style.display = "none";
      }}

      document.body.addEventListener(
        "mouseenter",
        (e) => {{
          const t = e.target;
          if (t && t.classList && t.classList.contains("info")) {{
            showFor(t, e.clientX, e.clientY);
          }}
        }},
        true,
      );
      document.body.addEventListener("mousemove", (e) => {{
        const t = e.target;
        if (t && t.classList && t.classList.contains("info")) {{
          showFor(t, e.clientX, e.clientY);
        }}
      }});
      document.body.addEventListener(
        "mouseleave",
        (e) => {{
          const t = e.target;
          if (t && t.classList && t.classList.contains("info")) {{
            hide();
          }}
        }},
        true,
      );
      window.addEventListener("scroll", hide, {{ passive: true }});
      window.addEventListener("blur", hide);
    }}

    function _readInputNum(id, fallback) {{
      const el = document.getElementById(id);
      if (!el) return fallback;
      const raw = String(el.value ?? "");
      const cleaned = raw.replaceAll(",", "").trim();
      const n = Number(cleaned);
      return Number.isFinite(n) ? n : fallback;
    }}

    function setupRerunControls() {{
      const runBtn = document.getElementById(\"runSim\");
      const statusEl = document.getElementById(\"runStatus\");
      const progEl = document.getElementById(\"runProg\");
      if (!runBtn || !statusEl || !progEl) return;

      function setStatus(s) {{
        statusEl.textContent = s;
      }}

      function setRunning(running) {{
        progEl.style.display = running ? \"block\" : \"none\";
        const ids = [
          \"csvPath\",
          \"timeframe\",
          \"initialNav\",
          \"aggr\",
          \"levCap\",
          \"venueCap\",
          \"maxDd\",
          \"liqBuf\",
          \"dirRisk\",
        ];
        for (const id of ids) {{
          const el = document.getElementById(id);
          if (el) el.disabled = running;
        }}
      }}

      async function ping() {{
        try {{
          const r = await fetch(`${{API_BASE}}/api/ping`, {{ cache: \"no-store\" }});
          return r.ok;
        }} catch {{
          return false;
        }}
      }}

      function buildRunRequest() {{
        const levRaw = _readInputNum(\"levCap\", 1.5);
        const venueRaw = _readInputNum(\"venueCap\", 0.30);
        return {{
          csv: _readInputStr(\"csvPath\", \"data/hyperliquid_btc_1h.csv\"),
          timeframe: _readInputStr(\"timeframe\", \"1h\"),
          fill_missing: true,
          initial_nav: _readInputNum(\"initialNav\", 10_000),
          aggressiveness: clamp(_readInputNum(\"aggr\", 0.5), 0, 1),
          leverage_cap: levRaw,
          venue_cap_frac: venueRaw,
          max_drawdown: clamp(_readInputNum(\"maxDd\", 0.2), 0, 1),
          liquidation_buffer: clamp(_readInputNum(\"liqBuf\", 0.1), 0, 1),
          target_dir_vol: clamp(_readInputNum(\"dirRisk\", 0.01), 0, 10),
        }};
      }}

      function normalizeInputs() {{
        const init = _readInputNum(\"initialNav\", 10_000);
        const lev = _readInputNum(\"levCap\", 1.5);
        const venue = _readInputNum(\"venueCap\", 0.30);
        const dir = clamp(_readInputNum(\"dirRisk\", 0.01), 0, 10);

        const initEl = document.getElementById(\"initialNav\");
        if (initEl) {{
          initEl.value = Number(init).toLocaleString(undefined, {{ maximumFractionDigits: 0 }});
        }}
        const levEl = document.getElementById(\"levCap\");
        if (levEl) levEl.value = String(lev);
        const venueEl = document.getElementById(\"venueCap\");
        if (venueEl) venueEl.value = String(venue);
        const dirEl = document.getElementById(\"dirRisk\");
        if (dirEl) dirEl.value = String(dir);
      }}

      async function runSimulation() {{
        normalizeInputs();
        runBtn.disabled = true;
        setRunning(true);
        const t0 = performance.now();
        setStatus(\"Running simulation…\");
        try {{
          const body = buildRunRequest();
          const r = await fetch(`${{API_BASE}}/api/run`, {{
            method: \"POST\",
            cache: \"no-store\",
            headers: {{ \"Content-Type\": \"application/json\" }},
            body: JSON.stringify(body),
          }});
          const data = await r.json();
          if (!r.ok || data.error) {{
            throw new Error(data.error || `HTTP ${{r.status}}`);
          }}
          renderDashboard(data);
          // Force a layout pass so canvases resize correctly.
          setTimeout(() => window.dispatchEvent(new Event(\"resize\")), 0);
          const dt = (performance.now() - t0) / 1000.0;
          setStatus(`Updated in ${{dt.toFixed(2)}}s.`);
        }} catch (e) {{
          const msg = (e && e.message) ? e.message : String(e);
          setStatus(`Run failed: ${{msg}}`);
        }} finally {{
          runBtn.disabled = false;
          setRunning(false);
        }}
      }}

      (async () => {{
        // Try same-origin first; if the dashboard is served via a static server (e.g. :5500),
        // fallback to the dashboard API server on :8000 with CORS enabled.
        API_BASE = \"\";
        const ok = await ping();
        if (ok) {{
          runBtn.disabled = false;
          setStatus(\"Server connected. Adjust params then click Run Simulation.\");
        }} else {{
          API_BASE = \"http://127.0.0.1:8000\";
          const ok2 = await ping();
          if (ok2) {{
            runBtn.disabled = false;
            setStatus(\"Connected to local API at http://127.0.0.1:8000. Press Run Simulation.\");
          }} else {{
            runBtn.disabled = true;
            setStatus(
              \"Run requires local server. Start: .venv/bin/python scripts/serve_dashboard.py \" +
                \"and open http://127.0.0.1:8000/\"
            );
          }}
        }}
      }})();

      runBtn.addEventListener(\"click\", runSimulation);

      const clampIds = [\"initialNav\", \"levCap\", \"venueCap\", \"dirRisk\"];
      for (const id of clampIds) {{
        const el = document.getElementById(id);
        if (el) {{
          el.addEventListener(\"blur\", normalizeInputs);
        }}
      }}
    }}

    document.getElementById("themeBtn").addEventListener("click", () => {{
      document.body.classList.toggle("light");
    }});

    setupRerunControls();
    setupInfoTips();
    main();
  </script>
</body>
</html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an interactive dark-mode HTML dashboard.")
    parser.add_argument("--title", default="Trading Dashboard")
    parser.add_argument(
        "--bars",
        type=Path,
        default=None,
        help="Backtest bars CSV from backtest.run --output-bars",
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        default=None,
        help="Metrics CSV from backtest.run --output-metrics",
    )
    parser.add_argument(
        "--shadow",
        type=Path,
        default=None,
        help="Shadow log CSV from live.shadow_runner --output",
    )
    parser.add_argument(
        "--trades",
        type=Path,
        default=None,
        help="Backtest trades CSV from backtest.run --output-trades",
    )
    parser.add_argument("--output", type=Path, default=Path("dashboard.html"))
    args = parser.parse_args(argv)

    bars = _read_csv(args.bars) if args.bars is not None and args.bars.exists() else []
    metrics = _read_csv(args.metrics) if args.metrics is not None and args.metrics.exists() else []
    shadow = _read_csv(args.shadow) if args.shadow is not None and args.shadow.exists() else []
    trades = _read_csv(args.trades) if args.trades is not None and args.trades.exists() else []

    html = _build_html(title=args.title, bars=bars, metrics=metrics, shadow=shadow, trades=trades)
    args.output.write_text(html, encoding="utf-8")
    print(f"wrote dashboard to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
