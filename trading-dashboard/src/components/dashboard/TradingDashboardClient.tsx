"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { Panel } from "@/components/dashboard/Panel";
import { ChartPoint, ChartSeries, SvgChart } from "@/components/dashboard/SvgChart";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import {
  BarRow,
  DashboardPayload,
  LifecycleRow,
  ShadowRow,
  TradeRow
} from "@/lib/dashboard/types";
import { formatCompact, formatDate, formatDateTime, formatNumber, formatPercent } from "@/lib/format";

type LoadState =
  | { status: "loading"; data: null; error: null }
  | { status: "error"; data: null; error: string }
  | { status: "ready"; data: DashboardPayload; error: null };

type RunForm = {
  csvPath: string;
  csv4hPath: string;
  timeframe: string;
  fillMissing: boolean;
  carryEnabled: boolean;
  initialNav: string;
  aggressiveness: string;
  leverageCap: string;
  venueCapFrac: string;
  maxDrawdown: string;
  liquidationBuffer: string;
  targetDirVol: string;
  takerFeeBps: string;
  slippageBpsAt1xNav: string;
  orderLatencyBars: string;
  fillRangePosition: string;
  fillTimeFraction: string;
  directionalStopLossPct: string;
  directionalTakeProfitPct: string;
  directionalMaxHoldBars: string;
  carryRebalanceThresholdPct: string;
};

type ChartConfig = {
  id: string;
  title: string;
  subtitle: string;
  valueLabel: string;
  height: number;
  percent?: boolean;
  accent?: "primary" | "green" | "amber" | "white";
  points?: ChartPoint[];
  series?: ChartSeries[];
};

const defaultRunForm: RunForm = {
  csvPath: "data/hyperliquid_btc_1h.csv",
  csv4hPath: "data/hyperliquid_btc_4h.csv",
  timeframe: "1h",
  fillMissing: true,
  carryEnabled: true,
  initialNav: "10,000",
  aggressiveness: "0.5",
  leverageCap: "1.5",
  venueCapFrac: "30",
  maxDrawdown: "20",
  liquidationBuffer: "10",
  targetDirVol: "20",
  takerFeeBps: "5",
  slippageBpsAt1xNav: "10",
  orderLatencyBars: "1",
  fillRangePosition: "75",
  fillTimeFraction: "25",
  directionalStopLossPct: "2",
  directionalTakeProfitPct: "4",
  directionalMaxHoldBars: "24",
  carryRebalanceThresholdPct: "1"
};

function metricMap(payload: DashboardPayload): Map<string, number> {
  return new Map(payload.metrics.map((metric) => [metric.metric, metric.value]));
}

function pnlForBar(bar: BarRow): number {
  return bar.pnlPrice + bar.pnlFunding + bar.pnlFees + bar.pnlSlippage;
}

function toneFor(value: number): "supportive" | "neutral" | "adverse" {
  if (Math.abs(value) < 0.000001) return "neutral";
  return value > 0 ? "supportive" : "adverse";
}

function regimeClass(regime: string): string {
  if (regime === "RISK_ON") return "bg-supportive/15 text-[#56D8C6]";
  if (regime === "RISK_OFF") return "bg-adverse/15 text-[#EE6A7A]";
  return "bg-primary/10 text-primary";
}

function lifecyclePnlPct(row: LifecycleRow): number | null {
  const basis = row.entryPrice * row.qty;
  if (!Number.isFinite(basis) || basis === 0) return null;
  return row.pnlTotal / basis;
}

function StatPill({ value }: { value: number }) {
  const className = value >= 0 ? "text-[#56D8C6]" : "text-[#EE6A7A]";
  return <span className={`font-mono font-semibold ${className}`}>{formatNumber(value, 2)}</span>;
}

function DataTable({
  columns,
  rows,
  emptyLabel = "No rows"
}: {
  columns: string[];
  rows: Array<Array<string | number | JSX.Element>>;
  emptyLabel?: string;
}) {
  return (
    <div className="thin-scrollbar max-h-[330px] overflow-auto rounded-[10px] border border-uiBorderMedium bg-[#06111f]">
      <table className="w-full border-collapse text-left text-[12px]">
        <thead className="sticky top-0 z-10 bg-[#06111f] text-[11px] uppercase tracking-[0.11em] text-uiTextDim">
          <tr>
            {columns.map((column, columnIndex) => (
              <th key={`${column}-${columnIndex}`} className="border-b border-uiBorderMedium px-3 py-3 font-semibold">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.length ? (
            rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="transition hover:bg-uiHover">
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="whitespace-nowrap px-3 py-2.5 text-uiTextPrimary">
                    {cell}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-uiTextDim">
                {emptyLabel}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function buildKpis(payload: DashboardPayload) {
  const metrics = metricMap(payload);
  const bars = payload.bars;
  const lifecycles = payload.lifecycles;
  const directional = lifecycles.filter((row) => row.kind === "directional");
  const carry = lifecycles.filter((row) => row.kind === "carry");
  const navStart = metrics.get("initial_nav") ?? bars[0]?.nav ?? 0;
  const navEnd = bars[bars.length - 1]?.nav ?? 0;
  const totalReturn = navStart ? navEnd / navStart - 1 : 0;
  const directionalWinRate = directional.length
    ? directional.filter((row) => row.pnlTotal > 0).length / directional.length
    : 0;

  return [
    {
      label: "Ending NAV",
      value: `$${formatNumber(navEnd, 2)}`,
      changeText: formatPercent(totalReturn),
      tone: toneFor(totalReturn),
      tooltip: "Ending simulated portfolio equity and total return over the run."
    },
    {
      label: "Max DD",
      value: formatPercent(metrics.get("max_drawdown") ?? 0),
      tone: "adverse" as const,
      tooltip: "Maximum peak-to-trough drawdown on the NAV curve."
    },
    {
      label: "Sharpe",
      value: formatNumber(metrics.get("sharpe") ?? 0, 3),
      tone: toneFor(metrics.get("sharpe") ?? 0),
      tooltip: "Simplified Sharpe ratio computed from per-bar returns."
    },
    {
      label: "Directional Trades",
      value: `${directional.length} trades`,
      changeText: formatPercent(directionalWinRate),
      tone: toneFor(directionalWinRate - 0.5),
      tooltip: "Open-to-close directional overlay lifecycle count and win rate."
    },
    {
      label: "Carry Lifecycles",
      value: `${carry.length} cycles`,
      tooltip: "Regime-driven carry hedge lifecycles."
    },
    {
      label: "Execution Legs",
      value: `${formatNumber(payload.trades.length, 0)} legs`,
      tooltip: "Spot/perp execution legs emitted by the simulator."
    },
    {
      label: "Funding Share",
      value: formatPercent(metrics.get("funding_contribution") ?? 0),
      tone: toneFor(metrics.get("funding_contribution") ?? 0),
      tooltip: "Funding contribution divided by total PnL."
    },
    {
      label: "Exposure Use",
      value: `${formatNumber(metrics.get("exposure_utilization") ?? 0, 3)}x`,
      tooltip: "Average gross exposure divided by NAV."
    }
  ];
}

function Header({ payload }: { payload: DashboardPayload }) {
  const first = payload.bars[0]?.timestamp;
  const last = payload.bars[payload.bars.length - 1]?.timestamp;

  return (
    <header className="flex flex-col gap-5 border-b border-uiBorderMedium pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-primary">
          SSH Trader
        </p>
        <h1 className="text-3xl font-bold tracking-tight text-uiTextPrimary md:text-4xl">
          Trading Research Dashboard
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-uiTextDim">
          Regime, carry, directional overlay, execution legs, and TA context from the latest
          generated run.
        </p>
      </div>
      <div className="rounded-[10px] border border-uiBorderMedium bg-uiSurfaceGlassDeep px-4 py-3 text-right backdrop-blur-sm">
        <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-uiTextDim">
          Data Window
        </p>
        <p className="mt-1 font-mono text-sm font-semibold text-uiTextPrimary">
          {first ? formatDate(first) : "-"} / {last ? formatDate(last) : "-"}
        </p>
      </div>
    </header>
  );
}

function parseRunNumber(value: string): number {
  return Number(value.replace(/,/g, ""));
}

function cleanNumericInput(value: string, allowComma = false): string {
  const stripped = value.replace(allowComma ? /[^\d.,]/g : /[^\d.]/g, "").replace(/,/g, allowComma ? "," : "");
  const [head, ...tail] = stripped.split(".");
  return tail.length ? `${head}.${tail.join("")}` : head;
}

function clampNumberText(value: string, min: number, max: number, digits: number, allowComma = false): string {
  const parsed = parseRunNumber(value);
  const next = Math.min(max, Math.max(min, Number.isFinite(parsed) ? parsed : min));
  const formatted = next.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
  return allowComma ? formatted : formatted.replace(/,/g, "");
}

function cleanBoundedNumericInput(value: string, max: number, digits: number, allowComma = false): string {
  const cleaned = cleanNumericInput(value, allowComma);
  if (cleaned.trim() === "") return "";
  const parsed = parseRunNumber(cleaned);
  if (Number.isFinite(parsed) && parsed > max) {
    return clampNumberText(String(max), 0, max, digits, allowComma);
  }
  if (allowComma && Number.isFinite(parsed)) {
    return parsed.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: digits
    });
  }
  return cleaned;
}

function FieldInfo({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <span className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-uiTextDim">
      {label}
      <InfoTooltip
        content={
          <span>
            <span className="block font-semibold text-uiTextPrimary">{label}</span>
            <span>{tooltip}</span>
          </span>
        }
      >
        <button
          type="button"
          className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-primary/25 text-[9px] text-primary"
          aria-label={`${label} information`}
        >
          ?
        </button>
      </InfoTooltip>
    </span>
  );
}

function TextRunField({
  label,
  value,
  tooltip,
  onChange
}: {
  label: string;
  value: string;
  tooltip: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <FieldInfo label={label} tooltip={tooltip} />
      <input
        type="text"
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full rounded-lg border border-uiBorderMedium bg-[#06111f] px-3 font-mono text-sm text-uiTextPrimary outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/10"
      />
    </label>
  );
}

function NumberRunField({
  label,
  value,
  tooltip,
  unit,
  prefix,
  min,
  max,
  step,
  digits,
  allowComma = false,
  onChange
}: {
  label: string;
  value: string;
  tooltip: string;
  unit?: string;
  prefix?: string;
  min: number;
  max: number;
  step: string;
  digits: number;
  allowComma?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <FieldInfo label={label} tooltip={`${tooltip} Accepted range: ${min} to ${max}${unit ? ` ${unit}` : ""}.`} />
      <div className="flex h-10 items-center rounded-lg border border-uiBorderMedium bg-[#06111f] focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/10">
        {prefix ? <span className="pl-3 font-mono text-sm font-semibold text-uiTextDim">{prefix}</span> : null}
        <input
          type="text"
          aria-label={label}
          inputMode="decimal"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(event) => onChange(cleanBoundedNumericInput(event.target.value, max, digits, allowComma))}
          onBlur={(event) => onChange(clampNumberText(event.currentTarget.value, min, max, digits, allowComma))}
          className="h-full min-w-0 flex-1 bg-transparent px-3 font-mono text-sm text-uiTextPrimary outline-none"
        />
        {unit ? <span className="pr-3 text-xs font-bold text-uiTextDim">{unit}</span> : null}
      </div>
    </label>
  );
}

function ToggleInfo({
  label,
  checked,
  tooltip,
  onChange
}: {
  label: string;
  checked: boolean;
  tooltip: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="inline-flex items-center gap-2 text-sm font-semibold text-uiTextDim">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 accent-primary"
      />
      {label}
      <InfoTooltip
        content={
          <span>
            <span className="block font-semibold text-uiTextPrimary">{label}</span>
            <span>{tooltip}</span>
          </span>
        }
      >
        <button
          type="button"
          className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-primary/25 text-[9px] text-primary"
          aria-label={`${label} information`}
        >
          ?
        </button>
      </InfoTooltip>
    </label>
  );
}

function ExpandButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <InfoTooltip content={`Expand ${label} into a focused full-screen chart with the same hover guide and tooltip.`}>
      <button
        type="button"
        onClick={onClick}
        className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-uiBorderMedium text-[15px] font-bold text-uiTextDim transition hover:border-primary/50 hover:text-primary"
        aria-label={`Expand ${label}`}
      >
        ⤢
      </button>
    </InfoTooltip>
  );
}

function RenderChart({ config, height, framed }: { config: ChartConfig; height?: number; framed?: boolean }) {
  return (
    <SvgChart
      points={config.points}
      series={config.series}
      height={height ?? config.height}
      valueLabel={config.valueLabel}
      percent={config.percent}
      accent={config.accent}
      framed={framed}
    />
  );
}

function ChartPanel({ config, onExpand }: { config: ChartConfig; onExpand: (config: ChartConfig) => void }) {
  return (
    <Panel
      title={config.title}
      subtitle={config.subtitle}
      action={<ExpandButton label={config.title} onClick={() => onExpand(config)} />}
    >
      <RenderChart config={config} />
    </Panel>
  );
}

function ChartModal({ config, onClose }: { config: ChartConfig | null; onClose: () => void }) {
  if (!config) return null;
  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/75 p-5 backdrop-blur-sm">
      <div className="flex max-h-[92vh] w-full max-w-[1500px] flex-col rounded-[12px] border border-uiBorderStrong bg-[#06111f] p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-bold text-uiTextPrimary">{config.title}</h3>
            <p className="mt-1 text-sm font-semibold text-uiTextDim">{config.subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-lg border border-uiBorderMedium px-3 text-sm font-bold text-uiTextDim transition hover:border-primary/50 hover:text-primary"
          >
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1">
          <RenderChart config={config} height={650} />
        </div>
      </div>
    </div>
  );
}

function RunControls({
  form,
  isRunning,
  status,
  error,
  onChange,
  onSubmit
}: {
  form: RunForm;
  isRunning: boolean;
  status: string | null;
  error: string | null;
  onChange: (patch: Partial<RunForm>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <Panel title="Simulation Setup" subtitle="backtest, shadow mode, TA features">
      <form className="space-y-4" onSubmit={onSubmit}>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <TextRunField
            label="1H CSV path"
            value={form.csvPath}
            tooltip="Repository-relative source OHLCV file used for replay, backtest, and shadow mode."
            onChange={(value) => onChange({ csvPath: value })}
          />
          <TextRunField
            label="4H CSV path"
            value={form.csv4hPath}
            tooltip="Optional higher-timeframe OHLCV file used to build compression and confluence features."
            onChange={(value) => onChange({ csv4hPath: value })}
          />
          <label className="block">
            <FieldInfo label="Timeframe" tooltip="Bar interval passed to the simulator. Use 1h for the current Hyperliquid BTC dataset." />
            <select
              aria-label="Timeframe"
              value={form.timeframe}
              onChange={(event) => onChange({ timeframe: event.target.value })}
              className="h-10 w-full rounded-lg border border-uiBorderMedium bg-[#06111f] px-3 font-mono text-sm text-uiTextPrimary outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/10"
            >
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <NumberRunField
            label="Starting NAV"
            value={form.initialNav}
            tooltip="Initial simulated account equity before the first rebalance."
            prefix="$"
            min={1_000}
            max={10_000_000}
            step="100"
            digits={0}
            allowComma
            onChange={(value) => onChange({ initialNav: value })}
          />
          <NumberRunField
            label="Policy aggression"
            value={form.aggressiveness}
            tooltip="Scales target exposure from conservative to more aggressive. This stays bounded because it directly influences sizing."
            min={0}
            max={1}
            step="0.05"
            digits={2}
            onChange={(value) => onChange({ aggressiveness: value })}
          />
          <NumberRunField
            label="Portfolio leverage cap"
            value={form.leverageCap}
            tooltip="Maximum gross exposure divided by NAV. Kept below venue headline leverage because this is a portfolio risk cap, not an exchange UI slider."
            unit="x"
            min={0}
            max={5}
            step="0.1"
            digits={2}
            onChange={(value) => onChange({ leverageCap: value })}
          />
          <NumberRunField
            label="Venue cap"
            value={form.venueCapFrac}
            tooltip="Maximum share of NAV allowed on any single venue. The project risk rule caps this at 30%."
            unit="%"
            min={0}
            max={30}
            step="1"
            digits={0}
            onChange={(value) => onChange({ venueCapFrac: value })}
          />
          <NumberRunField
            label="Max drawdown"
            value={form.maxDrawdown}
            tooltip="Portfolio drawdown kill-switch threshold from peak NAV. The project default is 20%."
            unit="%"
            min={1}
            max={50}
            step="1"
            digits={0}
            onChange={(value) => onChange({ maxDrawdown: value })}
          />
          <NumberRunField
            label="Liquidation buffer"
            value={form.liquidationBuffer}
            tooltip="Required distance from liquidation used by the simulator before accepting exposure."
            unit="%"
            min={0}
            max={50}
            step="1"
            digits={0}
            onChange={(value) => onChange({ liquidationBuffer: value })}
          />
          <NumberRunField
            label="Directional target vol"
            value={form.targetDirVol}
            tooltip="Annualized target volatility for the directional overlay. Directional overlay is still gated by RISK_ON regime."
            unit="%"
            min={0}
            max={100}
            step="1"
            digits={0}
            onChange={(value) => onChange({ targetDirVol: value })}
          />
          <NumberRunField
            label="Taker fee"
            value={form.takerFeeBps}
            tooltip="Execution fee charged per trade leg in basis points."
            unit="bps"
            min={0}
            max={100}
            step="1"
            digits={0}
            onChange={(value) => onChange({ takerFeeBps: value })}
          />
          <NumberRunField
            label="Slippage"
            value={form.slippageBpsAt1xNav}
            tooltip="Estimated slippage in basis points at 1x NAV notional."
            unit="bps"
            min={0}
            max={500}
            step="1"
            digits={0}
            onChange={(value) => onChange({ slippageBpsAt1xNav: value })}
          />
          <NumberRunField
            label="Order latency"
            value={form.orderLatencyBars}
            tooltip="Number of completed candles after the signal before a queued order can execute."
            unit="bars"
            min={0}
            max={24}
            step="1"
            digits={0}
            onChange={(value) => onChange({ orderLatencyBars: value })}
          />
          <NumberRunField
            label="Fill time"
            value={form.fillTimeFraction}
            tooltip="Where inside the execution candle the order is timestamped."
            unit="%"
            min={0}
            max={99}
            step="1"
            digits={0}
            onChange={(value) => onChange({ fillTimeFraction: value })}
          />
          <NumberRunField
            label="Fill price"
            value={form.fillRangePosition}
            tooltip="Side-aware position inside the candle range. Higher values are more adverse for buys and less adverse for sells."
            unit="%"
            min={0}
            max={100}
            step="1"
            digits={0}
            onChange={(value) => onChange({ fillRangePosition: value })}
          />
          <NumberRunField
            label="Stop loss"
            value={form.directionalStopLossPct}
            tooltip="Directional position stop loss from entry price."
            unit="%"
            min={0}
            max={50}
            step="1"
            digits={0}
            onChange={(value) => onChange({ directionalStopLossPct: value })}
          />
          <NumberRunField
            label="Take profit"
            value={form.directionalTakeProfitPct}
            tooltip="Directional position take profit from entry price."
            unit="%"
            min={0}
            max={100}
            step="1"
            digits={0}
            onChange={(value) => onChange({ directionalTakeProfitPct: value })}
          />
          <NumberRunField
            label="Max hold"
            value={form.directionalMaxHoldBars}
            tooltip="Maximum directional position lifetime."
            unit="bars"
            min={1}
            max={500}
            step="1"
            digits={0}
            onChange={(value) => onChange({ directionalMaxHoldBars: value })}
          />
          <NumberRunField
            label="Carry rebalance"
            value={form.carryRebalanceThresholdPct}
            tooltip="Ignore carry rebalance changes smaller than this target-drift threshold."
            unit="%"
            min={0}
            max={20}
            step="1"
            digits={0}
            onChange={(value) => onChange({ carryRebalanceThresholdPct: value })}
          />
        </div>

        <div className="flex flex-col gap-3 border-t border-uiBorderMedium pt-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-4">
            <ToggleInfo
              label="Fill missing bars"
              checked={form.fillMissing}
              tooltip="Forward-fills missing hourly candles before replay so the simulator sees a continuous time series."
              onChange={(checked) => onChange({ fillMissing: checked })}
            />
            <ToggleInfo
              label="Carry core enabled"
              checked={form.carryEnabled}
              tooltip="Keeps the delta-neutral carry leg active. Directional trades remain regime-gated separately."
              onChange={(checked) => onChange({ carryEnabled: checked })}
            />
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            {error ? <span className="max-w-[560px] text-sm font-semibold text-adverse">{error}</span> : null}
            {status ? <span className="text-sm font-semibold text-uiTextDim">{status}</span> : null}
            <button
              type="submit"
              disabled={isRunning}
              className="h-10 rounded-lg border border-primary/30 bg-primary px-4 text-sm font-bold text-[#03120f] transition hover:bg-[#35f7dd] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isRunning ? "Running..." : "Run Simulation"}
            </button>
          </div>
        </div>
      </form>
    </Panel>
  );
}

function ShadowTable({ rows }: { rows: ShadowRow[] }) {
  const recent = rows.slice(-14).reverse();
  return (
    <DataTable
      columns={["Time", "Regime", "Order", "Fill", "Slip", "Reason"]}
      rows={recent.map((row) => [
        <span key="time" className="font-mono text-uiTextDim">
          {formatDateTime(row.timestamp)}
        </span>,
        <span key="regime" className={`rounded-full px-2 py-1 text-[11px] font-bold ${regimeClass(row.regime)}`}>
          {row.regime}
        </span>,
        row.intendedOrder || "-",
        row.hypotheticalFill || "-",
        formatNumber(row.slippageEstimateBps, 3),
        row.reason || "-"
      ])}
    />
  );
}

function ExecutionTable({ rows }: { rows: TradeRow[] }) {
  return (
    <DataTable
      columns={["Time", "Leg", "Source", "Qty", "Price", "Notional", "Fee", "Slip"]}
      rows={rows.slice(-18).reverse().map((row) => [
        <span key="time" className="font-mono text-uiTextDim">
          {formatDateTime(row.ts)}
        </span>,
        row.leg,
        <span key="source" className="rounded-full bg-primary/10 px-2 py-1 text-[11px] font-bold text-primary">
          {row.source}
        </span>,
        formatCompact(row.qtyDelta),
        formatNumber(row.price, 2),
        formatCompact(row.notional),
        formatCompact(row.fee),
        formatCompact(row.slippage)
      ])}
    />
  );
}

function LifecycleTable({ rows, title }: { rows: LifecycleRow[]; title: string }) {
  return (
    <Panel title={title} subtitle="open to close">
      <DataTable
        columns={["Open", "Close", "Side", "Qty", "Entry", "Exit", "PnL", "PnL %", "Bars", "Reason"]}
        rows={rows.slice(-12).reverse().map((row) => [
          <span key="open" className="font-mono text-uiTextDim">
            {formatDateTime(row.openTs)}
          </span>,
          <span key="close" className="font-mono text-uiTextDim">
            {formatDateTime(row.closeTs)}
          </span>,
          row.side,
          formatCompact(row.qty),
          formatNumber(row.entryPrice, 2),
          formatNumber(row.exitPrice, 2),
          <StatPill key="pnl" value={row.pnlTotal} />,
          <span key="pnl-pct" className={row.pnlTotal >= 0 ? "text-[#56D8C6]" : "text-[#EE6A7A]"}>
            {formatPercent(lifecyclePnlPct(row) ?? 0)}
          </span>,
          String(row.barsHeld),
          row.exitReason || "-"
        ])}
      />
    </Panel>
  );
}

export function TradingDashboardClient() {
  const [state, setState] = useState<LoadState>({ status: "loading", data: null, error: null });
  const [runForm, setRunForm] = useState<RunForm>(defaultRunForm);
  const [isRunning, setIsRunning] = useState(false);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [expandedChart, setExpandedChart] = useState<ChartConfig | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/dashboard", { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.message ?? payload?.error ?? "Request failed");
        return payload as DashboardPayload;
      })
      .then((payload) => {
        if (!cancelled) setState({ status: "ready", data: payload, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            data: null,
            error: error instanceof Error ? error.message : "Unknown error"
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const payload = state.data;
  const kpis = useMemo(() => (payload ? buildKpis(payload) : []), [payload]);
  const metrics = useMemo(() => (payload ? metricMap(payload) : new Map<string, number>()), [payload]);
  const navSeries = useMemo(
    () => payload?.bars.map((bar) => ({ timestamp: bar.timestamp, value: bar.nav })) ?? [],
    [payload]
  );
  const buyHoldSeries = useMemo(() => {
    if (!payload?.bars.length) return [];
    const firstBar = payload.bars[0];
    const initialNav = metrics.get("initial_nav") ?? firstBar.nav;
    const startPrice = firstBar.price;
    if (!Number.isFinite(startPrice) || startPrice === 0) return [];
    return payload.bars.map((bar) => ({
      timestamp: bar.timestamp,
      value: initialNav * (bar.price / startPrice)
    }));
  }, [metrics, payload]);
  const priceSeries = useMemo(
    () => payload?.bars.map((bar) => ({ timestamp: bar.timestamp, value: bar.price })) ?? [],
    [payload]
  );
  const leverageSeries = useMemo(
    () => payload?.bars.map((bar) => ({ timestamp: bar.timestamp, value: bar.leverage })) ?? [],
    [payload]
  );
  const exposureSeries = useMemo(
    () =>
      payload?.bars.map((bar) => ({
        timestamp: bar.timestamp,
        value: bar.nav ? bar.grossExposure / bar.nav : 0
      })) ?? [],
    [payload]
  );

  async function runSimulation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsRunning(true);
    setRunError(null);
    setRunStatus("Running backtest, shadow mode, and TA feature extraction...");
    try {
      const response = await fetch("/api/dashboard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...runForm,
          initialNav: parseRunNumber(runForm.initialNav),
          aggressiveness: parseRunNumber(runForm.aggressiveness),
          leverageCap: parseRunNumber(runForm.leverageCap),
          venueCapFrac: parseRunNumber(runForm.venueCapFrac) / 100,
          maxDrawdown: parseRunNumber(runForm.maxDrawdown) / 100,
          liquidationBuffer: parseRunNumber(runForm.liquidationBuffer) / 100,
          targetDirVol: parseRunNumber(runForm.targetDirVol) / 100,
          takerFeeBps: parseRunNumber(runForm.takerFeeBps),
          slippageBpsAt1xNav: parseRunNumber(runForm.slippageBpsAt1xNav),
          orderLatencyBars: parseRunNumber(runForm.orderLatencyBars),
          fillRangePosition: parseRunNumber(runForm.fillRangePosition) / 100,
          fillTimeFraction: parseRunNumber(runForm.fillTimeFraction) / 100,
          directionalStopLossPct: parseRunNumber(runForm.directionalStopLossPct) / 100,
          directionalTakeProfitPct: parseRunNumber(runForm.directionalTakeProfitPct) / 100,
          directionalMaxHoldBars: parseRunNumber(runForm.directionalMaxHoldBars),
          carryRebalanceThresholdPct: parseRunNumber(runForm.carryRebalanceThresholdPct) / 100
        })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result?.message ?? result?.error ?? "Simulation failed");
      setState({ status: "ready", data: result as DashboardPayload, error: null });
      setRunStatus("Run complete. Dashboard updated from out/next-dashboard.");
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Unknown run error");
      setRunStatus(null);
    } finally {
      setIsRunning(false);
    }
  }
  const compressionSeries = useMemo(
    () =>
      payload?.taFeatures.map((row) => ({
        timestamp: row.timestamp,
        value: row.confluenceLong ?? row.confluenceShort ?? 0
      })) ?? [],
    [payload]
  );
  const chartConfigs = useMemo(
    () => ({
      nav: {
        id: "nav",
        title: "NAV vs Buy & Hold",
        subtitle: "portfolio equity",
        valueLabel: "NAV (USD)",
        height: 335,
        series: [
          { label: "Strategy NAV", points: navSeries, color: "#07DFC1", fill: true },
          { label: "Buy & hold NAV", points: buyHoldSeries, color: "rgba(239,254,235,0.76)", dashed: true }
        ]
      },
      ta: {
        id: "ta",
        title: "TA Confluence",
        subtitle: "compression and trigger context",
        valueLabel: "TA confluence",
        height: 255,
        points: compressionSeries,
        accent: "green" as const
      },
      price: {
        id: "price",
        title: "Price",
        subtitle: "underlying close",
        valueLabel: "Price (USD)",
        height: 320,
        points: priceSeries,
        accent: "white" as const
      },
      leverage: {
        id: "leverage",
        title: "Leverage",
        subtitle: "gross exposure / NAV",
        valueLabel: "Leverage",
        height: 320,
        points: leverageSeries,
        accent: "green" as const
      },
      exposure: {
        id: "exposure",
        title: "Exposure",
        subtitle: "gross exposure % NAV",
        valueLabel: "Exposure",
        height: 320,
        points: exposureSeries,
        percent: true,
        accent: "amber" as const
      }
    }),
    [buyHoldSeries, compressionSeries, exposureSeries, leverageSeries, navSeries, priceSeries]
  );

  if (state.status === "loading") {
    return (
      <div className="mx-auto flex min-h-screen max-w-[1480px] flex-col gap-5 px-5 py-8">
        <div className="dashboard-skeleton h-16 rounded-[10px]" />
        <div className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <KpiCard key={index} label="Loading" value="" tooltip="Loading dashboard data." isLoading />
          ))}
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mx-auto max-w-3xl px-5 py-10">
        <div className="rounded-[10px] border border-adverse/30 bg-adverse/10 p-5 text-adverse">
          <h1 className="text-xl font-bold">Dashboard data failed to load</h1>
          <p className="mt-2 text-sm text-textMuted">{state.error}</p>
        </div>
      </div>
    );
  }

  if (!payload) {
    return null;
  }

  return (
    <div className="mx-auto flex max-w-[1480px] flex-col gap-5 px-5 py-8">
      <Header payload={payload} />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} {...kpi} />
        ))}
      </section>

      <RunControls
        form={runForm}
        isRunning={isRunning}
        status={runStatus}
        error={runError}
        onChange={(patch) => setRunForm((current) => ({ ...current, ...patch }))}
        onSubmit={runSimulation}
      />

      <section className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <ChartPanel config={chartConfigs.nav} onExpand={setExpandedChart} />
        <Panel title="Regime Snapshot" subtitle="latest bar">
          <div className="space-y-5">
            {payload.bars.slice(-1).map((bar) => (
              <div key={bar.timestamp}>
                <span className={`rounded-full px-2 py-1 text-[11px] font-bold ${regimeClass(bar.regime)}`}>
                  {bar.regime}
                </span>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-uiTextDim">NAV</dt>
                    <dd className="font-mono font-semibold">{formatNumber(bar.nav, 2)}</dd>
                  </div>
                  <div>
                    <dt className="text-uiTextDim">Bar PnL</dt>
                    <dd className="font-mono font-semibold">{formatNumber(pnlForBar(bar), 2)}</dd>
                  </div>
                  <div>
                    <dt className="text-uiTextDim">Leverage</dt>
                    <dd className="font-mono font-semibold">{formatNumber(bar.leverage, 3)}</dd>
                  </div>
                  <div>
                    <dt className="text-uiTextDim">Gross Exposure</dt>
                    <dd className="font-mono font-semibold">{formatCompact(bar.grossExposure)}</dd>
                  </div>
                </dl>
              </div>
            ))}
            <div className="border-t border-uiBorderMedium pt-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div>
                  <p className="text-[13px] font-bold text-uiTextPrimary">TA Confluence</p>
                  <p className="text-[11px] font-semibold text-uiTextDim">latest regime inputs</p>
                </div>
                <ExpandButton label="TA Confluence" onClick={() => setExpandedChart(chartConfigs.ta)} />
              </div>
              <RenderChart config={chartConfigs.ta} framed={false} />
            </div>
          </div>
        </Panel>
      </section>

      <section className="grid gap-5">
        <ChartPanel config={chartConfigs.price} onExpand={setExpandedChart} />
        <ChartPanel config={chartConfigs.leverage} onExpand={setExpandedChart} />
        <ChartPanel config={chartConfigs.exposure} onExpand={setExpandedChart} />
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <Panel title="Shadow Events" subtitle="most recent rows">
          <ShadowTable rows={payload.shadow} />
        </Panel>
        <Panel title="Execution Legs" subtitle="spot/perp simulator legs">
          <ExecutionTable rows={payload.trades} />
        </Panel>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <LifecycleTable
          title="Directional Overlay Trades"
          rows={payload.lifecycles.filter((row) => row.kind === "directional")}
        />
        <LifecycleTable
          title="Carry Core Lifecycles"
          rows={payload.lifecycles.filter((row) => row.kind === "carry")}
        />
      </section>
      <ChartModal config={expandedChart} onClose={() => setExpandedChart(null)} />
    </div>
  );
}
