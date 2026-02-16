#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
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
      display: block;
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
    .card.hi {{
      box-shadow: 0 10px 30px var(--shadow), 0 0 0 1px rgba(255,255,255,0.02),
        0 0 50px var(--glow);
    }}
    .label {{ color: var(--muted); font-size: 0.82rem; margin-bottom: 6px; }}
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
        <div class="sub">Backtest and shadow-mode outcome viewer</div>
      </div>
      <button id="themeBtn" class="btn">Toggle Theme</button>
    </div>

    <div id="kpis" class="grid"></div>

    <div class="card">
      <div class="section-title">
        <div>Rerun Simulation</div>
        <div class="hint">Run button works when served locally</div>
      </div>
      <div class="controls">
        <div class="field">
          <label for="csvPath">CSV path</label>
          <input id="csvPath" value="data/hyperliquid_btc_1h.csv" />
        </div>
        <div class="field">
          <label for="timeframe">Timeframe</label>
          <input id="timeframe" value="1h" />
        </div>
        <div class="field">
          <label for="initialNav">Starting NAV (USD)</label>
          <input id="initialNav" value="1000000" />
        </div>
        <div class="field">
          <label for="aggr">Guidance aggressiveness (0..1)</label>
          <input id="aggr" value="0.5" />
        </div>
        <div class="field">
          <label for="levCap">Leverage cap</label>
          <input id="levCap" value="1.5" />
        </div>
        <div class="field">
          <label for="venueCap">Venue cap (0..1)</label>
          <input id="venueCap" value="0.3" />
        </div>
        <div class="field">
          <label for="maxDd">Max drawdown (0..1)</label>
          <input id="maxDd" value="0.2" />
        </div>
        <div class="field">
          <label for="liqBuf">Liquidation buffer (0..1)</label>
          <input id="liqBuf" value="0.1" />
        </div>
      </div>
      <div class="actions">
        <button id="runSim" class="btn small">Run Simulation</button>
        <button id="copyCmd" class="btn small">Copy CLI Command</button>
        <div id="runStatus" class="note"></div>
      </div>
      <details style="margin-top: 10px;">
        <summary class="note">Advanced: CLI command</summary>
        <textarea id="cmdBox" class="cmd" readonly></textarea>
        <div class="note">
          If the Run button is disabled, start the server with `scripts/serve_dashboard.py`
          and open the dashboard at `http://127.0.0.1:8000/`.
        </div>
      </details>
    </div>

    <div class="row">
      <div class="card hi">
        <div class="section-title">
          <div>NAV</div>
          <div class="hint">Wheel zoom, drag pan, hover for tooltip</div>
        </div>
        <div class="chart-wrap">
          <canvas id="navCanvas"></canvas>
          <div id="navTip" class="tooltip mono"></div>
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

  <script>
    const DATA = {data_json};

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
      const title = helpText ? `title="${{helpText.replaceAll('"', "'")}}"` : "";
      return `<div class="card" ${{title}}>
        <div class="label">${{label}}</div>
        <div class="${{cls}}">${{value}}</div>
        ${{ex}}
      </div>`;
    }}

    function buildKpis(bars, metrics, shadow, trades) {{
      const kpis = [];
      const map = new Map(metrics.map(m => [m.metric, m.value]));

      const nav0 = bars.length ? toNum(bars[0].nav) : null;
      const navN = bars.length ? toNum(bars[bars.length - 1].nav) : null;
      const start = bars.length ? bars[0].timestamp : "";
      const end = bars.length ? bars[bars.length - 1].timestamp : "";
      const orderCount = shadow.reduce((acc, r) => {{
        return acc + ((r.intended_order || "").length ? 1 : 0);
      }}, 0);

      const pnl = (nav0 != null && navN != null) ? (navN - nav0) : null;
      const ret = (nav0 != null && navN != null && nav0 !== 0) ? ((navN / nav0) - 1) : null;

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
        "Starting NAV",
        nav0 == null ? "n/a" : fmt2(nav0),
        "USD",
        "Starting portfolio equity (simulated NAV) in USD."
      ));

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
      return kpis.slice(0, 12);
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
        const x0 = 46;
        const y0 = 16;
        const x1 = w - 12;
        const y1 = h - 28;

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

        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim();
        ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";
        ctx.fillText(fmt3(yMax), 8, y0 + 6);
        ctx.fillText(fmt3(yMin), 8, y1 + 4);

        // Trade markers
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

        ctx.strokeStyle = opts.color;
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        let started = false;
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
            started = true;
          }} else {{
            ctx.lineTo(xx, yy);
          }}
        }}
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
            ctx.fillText(label, clamp(xx - wLab / 2, x0, x1 - wLab), h - 10);
          }}
        }}
      }}

      function idxAt(clientX) {{
        const rect = canvas.getBoundingClientRect();
        const w = rect.width;
        const x0 = 46;
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
        const x0 = 46;
        const y0 = 16;
        const x1 = w - 12;
        const y1 = h - 28;

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

        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--muted").trim();
        ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";
        ctx.fillText(fmt3(yMax), 8, y0 + 6);
        ctx.fillText(fmt3(yMin), 8, y1 + 4);

        for (let si = 0; si < seriesList.length; si++) {{
          const s = seriesList[si];
          ctx.strokeStyle = opts.colors[si];
          ctx.lineWidth = 2.0;
          ctx.beginPath();
          let started = false;
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
              started = true;
            }} else {{
              ctx.lineTo(xx, yy);
            }}
          }}
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
            ctx.fillText(label, clamp(xx - wLab / 2, x0, x1 - wLab), h - 10);
          }}
        }}
      }}

      function idxAt(clientX) {{
        const rect = canvas.getBoundingClientRect();
        const w = rect.width;
        const x0 = 46;
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

      const kpis = buildKpis(bars, metrics, shadow, trades);
      document.getElementById("kpis").innerHTML = kpis.join("");

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
      const levSeries = bars.map(b => ({{
        t: b.timestamp,
        y: toNum(b.leverage),
        meta: b,
      }}));

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
      const levCanvas = resetCanvas("levCanvas");
      const expCanvas = resetCanvas("expCanvas");

      makeChart(
        navCanvas,
        document.getElementById("navTip"),
        navSeries,
        {{
          color: "rgba(77,211,255,0.95)",
          label: "nav",
          markers: tradeMarkers,
          showRegimeDots: true,
          tooltip: (row) => {{
            const m = row.meta || {{}};
            const nav = toNum(m.nav);
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
            return [
              row.t,
              `NAV=${{fmt2(nav)}} USD`,
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

      makeChart(
        levCanvas,
        document.getElementById("levTip"),
        levSeries,
        {{
          color: "rgba(74,212,138,0.95)",
          label: "leverage",
          markers: tradeMarkers,
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
    }}

    function main() {{
      renderDashboard(DATA);
    }}

    function _readInputNum(id, fallback) {{
      const el = document.getElementById(id);
      if (!el) return fallback;
      const v = Number(el.value);
      return Number.isFinite(v) ? v : fallback;
    }}

    function _readInputStr(id, fallback) {{
      const el = document.getElementById(id);
      if (!el) return fallback;
      const s = String(el.value || "").trim();
      return s.length ? s : fallback;
    }}

    function _buildConfigJson() {{
      const initialNav = _readInputNum("initialNav", 10_000);
      const aggr = clamp(_readInputNum("aggr", 0.5), 0, 1);
      const levCap = _readInputNum("levCap", 15);
      const venueCap = clamp(_readInputNum("venueCap", 0.3), 0, 1);
      const maxDd = clamp(_readInputNum("maxDd", 0.2), 0, 1);
      const liqBuf = clamp(_readInputNum("liqBuf", 0.1), 0, 1);
      return {{
        data: {{ fill_missing: true }},
        guidance: {{ aggressiveness: aggr }},
        risk: {{
          leverage_cap: levCap,
          venue_cap_frac: venueCap,
          max_drawdown: maxDd,
          kill_switch_action: "carry_only",
        }},
        sim: {{
          initial_nav: initialNav,
          liquidation_buffer: liqBuf,
        }},
      }};
    }}

    function _buildRerunCommand() {{
      const csv = _readInputStr("csvPath", "data/hyperliquid_btc_1h.csv");
      const tf = _readInputStr("timeframe", "1h");
      const cfg = _buildConfigJson();
      const jsonStr = JSON.stringify(cfg, null, 2);
      const backtestCmd = [
        ".venv/bin/python -m ssh_trader.backtest.run",
        `--csv \"${{csv}}\"`,
        `--timeframe \"${{tf}}\"`,
        "--fill-missing",
        "--config out/dashboard_config.json",
        "--output-metrics out/metrics.csv",
        "--output-bars out/bars.csv",
        "--output-trades out/trades.csv",
      ].join(" ");
      const dashCmd = [
        ".venv/bin/python scripts/build_dashboard.py",
        `--title \"${{document.title}}\"`,
        "--bars out/bars.csv",
        "--metrics out/metrics.csv",
        "--shadow out/shadow_log.csv",
        "--trades out/trades.csv",
        "--output out/dashboard.html",
      ].join(" ");

      return [
        "# 1) Write config",
        "mkdir -p out",
        "cat > out/dashboard_config.json <<'JSON'",
        jsonStr,
        "JSON",
        "",
        "# 2) Run backtest (metrics + bars + trades)",
        backtestCmd,
        "",
        "# 3) Rebuild dashboard (shadow log optional)",
        dashCmd,
      ].join(\"\\n\");
    }}

    function setupRerunControls() {{
      const box = document.getElementById(\"cmdBox\");
      const btn = document.getElementById(\"copyCmd\");
      const runBtn = document.getElementById(\"runSim\");
      const statusEl = document.getElementById(\"runStatus\");
      if (!box || !btn || !runBtn || !statusEl) return;

      function refresh() {{
        box.value = _buildRerunCommand();
      }}

      const ids = [
        \"csvPath\",
        \"timeframe\",
        \"initialNav\",
        \"aggr\",
        \"levCap\",
        \"venueCap\",
        \"maxDd\",
        \"liqBuf\",
      ];
      for (const id of ids) {{
        const el = document.getElementById(id);
        if (el) {{
          el.addEventListener(\"input\", refresh);
        }}
      }}
      refresh();

      btn.addEventListener(\"click\", async () => {{
        const txt = box.value;
        try {{
          await navigator.clipboard.writeText(txt);
          btn.textContent = \"Copied!\";
          setTimeout(() => {{ btn.textContent = \"Copy Command\"; }}, 900);
        }} catch {{
          box.focus();
          box.select();
          document.execCommand(\"copy\");
        }}
      }});

      function setStatus(s) {{
        statusEl.textContent = s;
      }}

      async function ping() {{
        try {{
          const r = await fetch(\"/api/ping\", {{ cache: \"no-store\" }});
          return r.ok;
        }} catch {{
          return false;
        }}
      }}

      function buildRunRequest() {{
        return {{
          csv: _readInputStr(\"csvPath\", \"data/hyperliquid_btc_1h.csv\"),
          timeframe: _readInputStr(\"timeframe\", \"1h\"),
          fill_missing: true,
          initial_nav: _readInputNum(\"initialNav\", 10_000),
          aggressiveness: clamp(_readInputNum(\"aggr\", 0.5), 0, 1),
          leverage_cap: _readInputNum(\"levCap\", 15),
          venue_cap_frac: clamp(_readInputNum(\"venueCap\", 0.3), 0, 1),
          max_drawdown: clamp(_readInputNum(\"maxDd\", 0.2), 0, 1),
          liquidation_buffer: clamp(_readInputNum(\"liqBuf\", 0.1), 0, 1),
        }};
      }}

      async function runSimulation() {{
        runBtn.disabled = true;
        setStatus(\"Running…\");
        try {{
          const body = buildRunRequest();
          const r = await fetch(\"/api/run\", {{
            method: \"POST\",
            headers: {{ \"Content-Type\": \"application/json\" }},
            body: JSON.stringify(body),
          }});
          const data = await r.json();
          if (!r.ok || data.error) {{
            throw new Error(data.error || `HTTP ${{r.status}}`);
          }}
          renderDashboard(data);
          setStatus(\"Updated.\");
        }} catch (e) {{
          const msg = (e && e.message) ? e.message : String(e);
          setStatus(`Run failed: ${{msg}}`);
        }} finally {{
          runBtn.disabled = false;
        }}
      }}

      (async () => {{
        const ok = await ping();
        if (ok) {{
          runBtn.disabled = false;
          setStatus(\"Server connected. Adjust params then click Run Simulation.\");
        }} else {{
          runBtn.disabled = true;
          setStatus(
            \"Run requires local server. Start: .venv/bin/python scripts/serve_dashboard.py \" +
              \"and open http://127.0.0.1:8000/\"
          );
        }}
      }})();

      runBtn.addEventListener(\"click\", runSimulation);
    }}

    document.getElementById("themeBtn").addEventListener("click", () => {{
      document.body.classList.toggle("light");
    }});

    setupRerunControls();
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
