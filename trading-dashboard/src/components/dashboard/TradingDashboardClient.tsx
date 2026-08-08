"use client";

import { FormEvent, useCallback, useEffect, useId, useMemo, useRef, useState, useTransition } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { Panel } from "@/components/dashboard/Panel";
import { CandlePoint, ChartMarker, ChartPoint, ChartSeries, SvgChart } from "@/components/dashboard/SvgChart";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { ThemedSelect } from "@/components/ui/ThemedSelect";
import {
  BarRow,
  DashboardPayload,
  LifecycleRow,
  ShadowRow,
  TradeRow
} from "@/lib/dashboard/types";
import { formatCompact, formatDate, formatDateTime, formatNumber, formatPercent } from "@/lib/format";
import { dashboardColors } from "@/lib/dashboard/theme";

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
  candles?: CandlePoint[];
  defaultMode?: "line" | "candles";
  markers?: ChartMarker[];
  markerMode?: "native" | "trade";
  chartType?: "line" | "area" | "candles" | "histogram";
  stepped?: boolean;
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
  if (regime === "RISK_ON") return "bg-supportive/15 text-supportive";
  if (regime === "RISK_OFF") return "bg-adverse/15 text-adverse";
  return "bg-primary/10 text-primary";
}

function lifecyclePnlPct(row: LifecycleRow): number | null {
  const basis = row.entryPrice * row.qty;
  if (!Number.isFinite(basis) || basis === 0) return null;
  return row.pnlTotal / basis;
}

function lifecycleKey(row: LifecycleRow): string {
  return `${row.kind}:${row.openTs}:${row.closeTs}:${row.side}:${row.qty}`;
}

function timeMs(value: string): number {
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
}

function preferredScrollBehavior(): ScrollBehavior {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ? "auto"
    : "smooth";
}

function nearestByTime<T extends { timestamp: string }>(rows: T[], timestamp: string): T | null {
  if (!rows.length) return null;
  const target = timeMs(timestamp);
  return rows.reduce<T | null>((best, row) => {
    if (!best) return row;
    return Math.abs(timeMs(row.timestamp) - target) < Math.abs(timeMs(best.timestamp) - target) ? row : best;
  }, null);
}

function tradeLegsForLifecycle(row: LifecycleRow, trades: TradeRow[]): TradeRow[] {
  const open = timeMs(row.openTs);
  const close = timeMs(row.closeTs);
  return trades.filter((trade) => {
    const ts = timeMs(trade.ts);
    return trade.source === row.kind && ts >= open && ts <= close;
  });
}

function priceWindowForLifecycle(row: LifecycleRow, bars: BarRow[]): ChartPoint[] {
  const open = timeMs(row.openTs);
  const close = timeMs(row.closeTs);
  const duration = Math.max(60 * 60 * 1000, close - open);
  const context = Math.max(12 * 60 * 60 * 1000, duration * 0.75);
  const start = open - context;
  const end = close + context;
  return bars
    .filter((bar) => {
      const ts = timeMs(bar.timestamp);
      return ts >= start && ts <= end;
    })
    .map((bar) => ({ timestamp: bar.timestamp, value: bar.price }));
}

function tradeMarkersForPriceChart(rows: LifecycleRow[]): ChartMarker[] {
  return rows
    .filter((row) => row.kind === "directional")
    .flatMap((row) => {
      const openIsBuy = row.side !== "short";
      return [
        {
          timestamp: row.openTs,
          label: openIsBuy ? "Buy" : "Sell",
          color: openIsBuy ? dashboardColors.primary : dashboardColors.adverse
        },
        {
          timestamp: row.closeTs,
          label: openIsBuy ? "Sell" : "Buy",
          color: openIsBuy ? dashboardColors.adverse : dashboardColors.primary
        }
      ];
    });
}

function configuredEffectiveLeverageCap(form: RunForm): number {
  const cap = parseRunNumber(form.leverageCap);
  const liquidationBuffer = parseRunNumber(form.liquidationBuffer) / 100;
  return Math.max(0, cap * (1 - liquidationBuffer));
}

function StatPill({ value }: { value: number }) {
  const className = value >= 0 ? "text-supportive" : "text-adverse";
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
    <div className="thin-scrollbar max-h-[330px] overflow-auto rounded-[var(--radius-md)] border border-uiBorderMedium bg-[var(--bg-input)]">
      <table className="w-full border-collapse text-left text-[12px]">
        <thead className="sticky top-0 z-10 bg-[var(--bg-input)] text-[11px] uppercase tracking-[0.11em] text-uiTextDim">
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
    <header id="overview" className="scroll-mt-24 flex flex-col gap-4 border-b border-uiBorderMedium pb-5 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
          Overview
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-uiTextPrimary md:text-3xl">
          Trading Research
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-uiTextDim">
          Regime, carry, directional overlay, execution legs, and TA context from the latest
          generated run.
        </p>
      </div>
      <div className="rounded-[var(--radius-md)] border border-uiBorderMedium bg-uiSurfaceGlassDeep px-4 py-3 text-right">
        <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-uiTextDim">
          Data Window
        </p>
        <p className="mt-1 font-mono text-sm font-semibold text-uiTextPrimary">
          {first ? formatDate(first) : "-"} / {last ? formatDate(last) : "-"}
        </p>
        {payload.sampling.barsReturnedCount < payload.sampling.barsOriginalCount ? (
          <p className="mt-1 text-[11px] font-semibold text-uiTextDim">
            {formatNumber(payload.sampling.barsReturnedCount, 0)} chart points from {formatNumber(payload.sampling.barsOriginalCount, 0)} bars
          </p>
        ) : null}
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
    <span className="flex min-h-11 items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-uiTextDim">
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
          className="inline-flex h-11 w-11 items-center justify-center rounded-full text-[10px] text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
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
        className="h-11 w-full rounded-lg border border-uiBorderMedium bg-[var(--bg-input)] px-3 font-mono text-sm text-uiTextPrimary outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/30"
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
      <div className="flex h-11 items-center rounded-lg border border-uiBorderMedium bg-[var(--bg-input)] focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/30">
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
    <label className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-uiTextDim">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-6 w-6 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
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
          className="inline-flex h-11 w-11 items-center justify-center rounded-full text-[10px] text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
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
        className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-uiBorderMedium text-[15px] font-bold text-uiTextDim transition hover:border-primary/50 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
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
      candles={config.candles}
      defaultMode={config.defaultMode}
      markers={config.markers}
      markerMode={config.markerMode}
      height={height ?? config.height}
      valueLabel={config.valueLabel}
      percent={config.percent}
      accent={config.accent}
      framed={framed}
      chartType={config.chartType}
      stepped={config.stepped}
    />
  );
}

function SkeletonBlock({ className }: { className: string }) {
  return <div className={`dashboard-skeleton rounded ${className}`} />;
}

function HeaderSkeleton() {
  return (
    <header className="flex flex-col gap-4 border-b border-uiBorderMedium pb-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0 flex-1">
        <SkeletonBlock className="mb-3 h-3 w-20" />
        <SkeletonBlock className="h-8 w-full max-w-[360px]" />
        <SkeletonBlock className="mt-4 h-4 w-full max-w-[760px]" />
        <SkeletonBlock className="mt-2 h-4 w-3/5 max-w-[520px]" />
      </div>
      <div className="rounded-[var(--radius-md)] border border-uiBorderMedium bg-uiSurfaceGlassDeep px-4 py-3 lg:min-w-[255px]">
        <SkeletonBlock className="ml-auto h-3 w-24" />
        <SkeletonBlock className="ml-auto mt-3 h-5 w-44" />
      </div>
    </header>
  );
}

function FormFieldSkeleton() {
  return (
    <div>
      <SkeletonBlock className="mb-2 h-3 w-28" />
      <SkeletonBlock className="h-10 w-full rounded-lg" />
    </div>
  );
}

function RunControlsSkeleton() {
  return (
    <Panel title="Simulation Setup" subtitle="backtest, shadow mode, TA features">
      <div className="space-y-4" aria-hidden="true">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 20 }).map((_, index) => (
            <FormFieldSkeleton key={index} />
          ))}
        </div>
        <div className="flex flex-col gap-3 border-t border-uiBorderMedium pt-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-4">
            <SkeletonBlock className="h-5 w-40" />
            <SkeletonBlock className="h-5 w-40" />
          </div>
          <SkeletonBlock className="h-10 w-36 rounded-lg" />
        </div>
      </div>
    </Panel>
  );
}

function ChartPanelSkeleton({ title, subtitle, height = 320 }: { title: string; subtitle: string; height?: number }) {
  return (
    <Panel title={title} subtitle={subtitle} action={<SkeletonBlock className="h-7 w-7 rounded-lg" />}>
      <div className="rounded-[var(--radius-md)] border border-uiBorderMedium bg-[var(--bg-input)] p-3" aria-hidden="true">
        <div className="mb-4 flex items-center justify-between">
          <SkeletonBlock className="h-3 w-24" />
          <SkeletonBlock className="h-3 w-40" />
        </div>
        <div className="relative overflow-hidden rounded-md border border-primary/10 bg-[rgba(3,13,24,0.62)]" style={{ height }}>
          <SkeletonBlock className="absolute left-4 top-5 h-3 w-14" />
          <SkeletonBlock className="absolute left-4 top-[28%] h-3 w-20" />
          <SkeletonBlock className="absolute left-4 top-[52%] h-3 w-16" />
          <SkeletonBlock className="absolute left-4 top-[76%] h-3 w-20" />
          <div className="absolute inset-x-[11%] bottom-10 top-6">
            <SkeletonBlock className="h-full w-full rounded-md opacity-70" />
          </div>
          <SkeletonBlock className="absolute bottom-3 left-[12%] h-3 w-20" />
          <SkeletonBlock className="absolute bottom-3 left-[44%] h-3 w-20" />
          <SkeletonBlock className="absolute bottom-3 right-[8%] h-3 w-20" />
        </div>
      </div>
    </Panel>
  );
}

function RegimeSnapshotSkeleton() {
  return (
    <Panel title="Regime Snapshot" subtitle="latest bar">
      <div className="space-y-5" aria-hidden="true">
        <div>
          <SkeletonBlock className="h-6 w-24 rounded-full" />
          <dl className="mt-4 grid grid-cols-2 gap-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index}>
                <SkeletonBlock className="h-3 w-24" />
                <SkeletonBlock className="mt-2 h-4 w-20" />
              </div>
            ))}
          </dl>
        </div>
        <div className="border-t border-uiBorderMedium pt-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <SkeletonBlock className="h-4 w-28" />
              <SkeletonBlock className="mt-2 h-3 w-32" />
            </div>
            <SkeletonBlock className="h-7 w-7 rounded-lg" />
          </div>
          <div className="rounded-[var(--radius-md)] bg-[var(--bg-input)] p-3">
            <SkeletonBlock className="h-[255px] w-full rounded-md" />
          </div>
        </div>
      </div>
    </Panel>
  );
}

function DataTableSkeleton({ columns = 6, rows = 8 }: { columns?: number; rows?: number }) {
  return (
    <div className="thin-scrollbar max-h-[330px] overflow-hidden rounded-[var(--radius-md)] border border-uiBorderMedium bg-[var(--bg-input)]" aria-hidden="true">
      <div className="grid border-b border-uiBorderMedium px-3 py-3" style={{ gridTemplateColumns: `repeat(${columns}, minmax(88px, 1fr))` }}>
        {Array.from({ length: columns }).map((_, index) => (
          <SkeletonBlock key={index} className="h-3 w-16" />
        ))}
      </div>
      <div className="divide-y divide-white/5">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div key={rowIndex} className="grid px-3 py-3" style={{ gridTemplateColumns: `repeat(${columns}, minmax(88px, 1fr))` }}>
            {Array.from({ length: columns }).map((_, columnIndex) => (
              <SkeletonBlock key={columnIndex} className={`h-3 ${columnIndex % 3 === 0 ? "w-24" : columnIndex % 3 === 1 ? "w-16" : "w-20"}`} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function LifecycleTableSkeleton({ title }: { title: string }) {
  return (
    <Panel title={title} subtitle="open to close">
      <DataTableSkeleton columns={10} rows={7} />
    </Panel>
  );
}

function TradeInspectorSkeleton() {
  return (
    <section className="relative overflow-hidden rounded-[var(--radius-lg)] border border-uiBorderMedium bg-uiSurfaceGlassDeep shadow-2xl shadow-black/20" aria-hidden="true">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(7,223,193,0.018),transparent_34%)]" />
      <div className="relative">
        <div className="flex flex-col gap-4 border-b border-uiBorderMedium px-5 py-5 md:flex-row md:items-start md:justify-between">
          <div className="max-w-4xl flex-1">
            <div className="flex flex-wrap items-center gap-3">
              <SkeletonBlock className="h-8 w-48" />
              <SkeletonBlock className="h-7 w-24 rounded-md" />
            </div>
            <SkeletonBlock className="mt-4 h-5 w-72" />
            <SkeletonBlock className="mt-3 h-4 w-full max-w-3xl" />
            <SkeletonBlock className="mt-2 h-4 w-2/3 max-w-2xl" />
          </div>
          <div className="min-w-[150px]">
            <SkeletonBlock className="h-3 w-32 md:ml-auto" />
            <SkeletonBlock className="mt-5 h-3 w-20 md:ml-auto" />
            <SkeletonBlock className="mt-3 h-10 w-32 md:ml-auto" />
            <SkeletonBlock className="mt-3 h-4 w-24 md:ml-auto" />
          </div>
        </div>
        <div className="px-5 py-5">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div>
              <SkeletonBlock className="h-4 w-44" />
              <SkeletonBlock className="mt-2 h-4 w-64" />
            </div>
            <SkeletonBlock className="h-3 w-40" />
          </div>
          <div className="rounded-[var(--radius-md)] border border-uiBorderMedium bg-[var(--bg-input)] p-4">
            <SkeletonBlock className="h-[320px] w-full rounded-md" />
          </div>
        </div>
        <div className="grid border-t border-uiBorderMedium xl:grid-cols-[1fr_0.95fr]">
          <div className="px-5 py-5 xl:border-r xl:border-uiBorderMedium">
            <SkeletonBlock className="h-4 w-24" />
            <div className="mt-6 grid gap-x-8 gap-y-6 sm:grid-cols-2 xl:grid-cols-4">
              {Array.from({ length: 12 }).map((_, index) => (
                <div key={index}>
                  <SkeletonBlock className="h-3 w-24" />
                  <SkeletonBlock className="mt-2 h-4 w-28" />
                </div>
              ))}
            </div>
          </div>
          <div className="px-5 py-5">
            <SkeletonBlock className="h-4 w-32" />
            <div className="mt-6 grid grid-cols-2 gap-x-8 gap-y-6">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index}>
                  <SkeletonBlock className="h-3 w-20" />
                  <SkeletonBlock className="mt-2 h-4 w-24" />
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="border-t border-uiBorderMedium px-5 py-5">
          <SkeletonBlock className="h-4 w-32" />
          <div className="mt-6 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <div key={index}>
                <SkeletonBlock className="h-3 w-28" />
                <SkeletonBlock className="mt-2 h-4 w-16" />
              </div>
            ))}
          </div>
        </div>
        <div className="border-t border-uiBorderMedium px-5 py-5">
          <div className="mb-3 flex items-center justify-between">
            <SkeletonBlock className="h-4 w-44" />
            <SkeletonBlock className="h-3 w-32" />
          </div>
          <DataTableSkeleton columns={7} rows={5} />
        </div>
      </div>
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <div className="mx-auto flex min-h-screen max-w-[1760px] flex-col gap-5 px-5 py-8" aria-busy="true" aria-live="polite">
      <HeaderSkeleton />
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <KpiCard key={index} label="Loading" value="" tooltip="Loading dashboard data." isLoading />
        ))}
      </section>
      <section id="run" className="scroll-mt-24">
        <RunControlsSkeleton />
      </section>
      <section id="charts" className="scroll-mt-24 grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <ChartPanelSkeleton title="NAV vs Buy & Hold" subtitle="portfolio equity" height={335} />
        <RegimeSnapshotSkeleton />
      </section>
      <section className="grid gap-5">
        <ChartPanelSkeleton title="Price" subtitle="underlying close" />
        <ChartPanelSkeleton title="Leverage" subtitle="gross exposure / NAV" />
        <ChartPanelSkeleton title="Exposure" subtitle="gross exposure % NAV" />
      </section>
      <section id="events" className="scroll-mt-24 grid gap-5 xl:grid-cols-2">
        <Panel title="Shadow Events" subtitle="most recent rows">
          <DataTableSkeleton columns={6} rows={8} />
        </Panel>
        <Panel title="Execution Legs" subtitle="spot/perp simulator legs">
          <DataTableSkeleton columns={8} rows={8} />
        </Panel>
      </section>
      <section id="trades" className="scroll-mt-24 grid gap-5 xl:grid-cols-2">
        <LifecycleTableSkeleton title="Directional Overlay Trades" />
        <LifecycleTableSkeleton title="Carry Core Lifecycles" />
      </section>
    </div>
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

function ChartModal({ config, isLoading, onClose }: { config: ChartConfig | null; isLoading: boolean; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || !config) return;

    const previousOverflow = document.body.style.overflow;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const handleCancel = (event: Event) => {
      event.preventDefault();
      onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      onClose();
    };

    dialog.addEventListener("cancel", handleCancel);
    document.addEventListener("keydown", handleKeyDown);
    if (!dialog.open) dialog.showModal();
    document.body.style.overflow = "hidden";
    dialog.querySelector<HTMLButtonElement>("button")?.focus();

    return () => {
      dialog.removeEventListener("cancel", handleCancel);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      if (dialog.open) dialog.close();
      previouslyFocused?.focus();
    };
  }, [config, onClose]);

  if (!config) return null;
  const modalChartHeight = typeof window === "undefined" ? 620 : Math.max(300, Math.min(700, window.innerHeight - 220));

  return (
    <dialog
      ref={dialogRef}
      aria-modal="true"
      aria-labelledby={titleId}
      className="m-auto max-h-[92vh] w-[calc(100%-2rem)] max-w-[1720px] bg-transparent p-0 text-uiTextPrimary backdrop:bg-black/75 backdrop:backdrop-blur-sm"
    >
      <div className="flex max-h-[92vh] min-w-0 flex-col rounded-[var(--radius-lg)] border border-uiBorderStrong bg-uiSurfaceGlassDeep px-4 py-5 shadow-2xl sm:px-8 sm:py-7">
        <div className="mb-6 flex items-center justify-between gap-6">
          <div className="min-w-0">
            <h2 id={titleId} className="text-xl font-bold text-uiTextPrimary">{config.title}</h2>
            <p className="mt-1 text-sm font-semibold text-uiTextDim">{config.subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="h-11 shrink-0 rounded-[var(--radius-sm)] border border-uiBorderMedium px-5 font-mono text-sm font-bold text-uiTextDim transition hover:border-primary/50 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
          >
            Close
          </button>
        </div>
        <div className="min-h-0 min-w-0 flex-1 overflow-auto pb-2">
          {isLoading ? <ChartModalSkeleton height={modalChartHeight} /> : <RenderChart config={config} height={modalChartHeight} />}
        </div>
      </div>
    </dialog>
  );
}

function ChartModalSkeleton({ height }: { height: number }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-uiBorderMedium bg-[var(--bg-surface)] p-4" aria-busy="true" aria-live="polite">
      <div className="mb-3 flex items-center justify-between gap-3">
        <SkeletonBlock className="h-3 w-32" />
        <div className="flex gap-2">
          <SkeletonBlock className="h-7 w-28 rounded-md" />
          <SkeletonBlock className="h-7 w-16 rounded-md" />
        </div>
      </div>
      <div className="dashboard-skeleton w-full rounded-[var(--radius-sm)]" style={{ height }} />
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
            <ThemedSelect
              aria-label="Timeframe"
              value={form.timeframe}
              onChange={(timeframe) => onChange({ timeframe })}
              options={[
                { value: "1h", label: "1h" },
                { value: "4h", label: "4h" },
                { value: "1d", label: "1d" }
              ]}
            />
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
            tooltip="System-level gross exposure limit divided by NAV. The simulator also applies the liquidation buffer, so the enforced cap is lower than this input."
            unit="x"
            min={0.1}
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
              className="h-11 rounded-lg border border-primary/30 bg-primary px-4 text-sm font-bold text-primaryText transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-60"
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

function DetailItem({ label, value, tone }: { label: string; value: string; tone?: "supportive" | "adverse" }) {
  const toneClass = tone === "supportive" ? "text-supportive" : tone === "adverse" ? "text-adverse" : "text-uiTextPrimary";
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-[0.15em] text-uiTextDim">{label}</dt>
      <dd className={`mt-1 font-mono text-[15px] font-semibold ${toneClass}`}>{value}</dd>
    </div>
  );
}

function InspectorSectionTitle({ children }: { children: string }) {
  return (
    <h4 className="font-mono text-[12px] font-semibold uppercase tracking-[0.18em] text-uiTextSecondary">
      // {children}
    </h4>
  );
}

function LifecycleTable({
  rows,
  title,
  selectedKey,
  onSelect
}: {
  rows: LifecycleRow[];
  title: string;
  selectedKey: string | null;
  onSelect: (row: LifecycleRow) => void;
}) {
  const visibleRows = rows.slice(-12).reverse();
  return (
    <Panel title={title} subtitle="open to close">
      <div className="thin-scrollbar max-h-[330px] overflow-auto rounded-[var(--radius-md)] border border-uiBorderMedium bg-[var(--bg-input)]">
        <table className="w-full border-collapse text-left text-[12px]">
          <thead className="sticky top-0 z-10 bg-[var(--bg-input)] text-[11px] uppercase tracking-[0.11em] text-uiTextDim">
            <tr>
              {["Open", "Close", "Side", "Qty", "Entry", "Exit", "PnL", "PnL %", "Bars", "Reason"].map((column) => (
                <th key={column} className="border-b border-uiBorderMedium px-3 py-3 font-semibold">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {visibleRows.length ? (
              visibleRows.map((row) => {
                const key = lifecycleKey(row);
                const isSelected = key === selectedKey;
                return (
                  <tr
                    key={key}
                    className={`cursor-pointer transition ${isSelected ? "bg-primary/10 ring-1 ring-inset ring-primary/30" : "hover:bg-uiHover"}`}
                    onClick={() => onSelect(row)}
                  >
                    <td className="whitespace-nowrap px-3 py-1.5 font-mono text-uiTextDim">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelect(row);
                        }}
                        className="min-h-11 rounded-md px-1 text-left underline-offset-4 hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                        aria-label={`Inspect ${row.kind} lifecycle opened ${formatDateTime(row.openTs)}`}
                      >
                        {formatDateTime(row.openTs)}
                      </button>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 font-mono text-uiTextDim">{formatDateTime(row.closeTs)}</td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-uiTextPrimary">{row.side}</td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-uiTextPrimary">{formatCompact(row.qty)}</td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-uiTextPrimary">{formatNumber(row.entryPrice, 2)}</td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-uiTextPrimary">{formatNumber(row.exitPrice, 2)}</td>
                    <td className="whitespace-nowrap px-3 py-2.5"><StatPill value={row.pnlTotal} /></td>
                    <td className={`whitespace-nowrap px-3 py-2.5 ${row.pnlTotal >= 0 ? "text-supportive" : "text-adverse"}`}>
                      {formatPercent(lifecyclePnlPct(row) ?? 0)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-uiTextPrimary">{String(row.barsHeld)}</td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-uiTextPrimary">{row.exitReason || "-"}</td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={10} className="px-3 py-6 text-center text-uiTextDim">No lifecycle rows</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function TradeInspector({
  row,
  payload
}: {
  row: LifecycleRow | null;
  payload: DashboardPayload;
}) {
  if (!row) {
    return (
      <Panel title="Trade Inspector" subtitle="select a lifecycle">
        <div className="rounded-[var(--radius-md)] border border-uiBorderMedium bg-[var(--bg-input)] p-5 text-sm text-uiTextDim">
          Select a directional or carry lifecycle row to inspect entry, close, position, and signal context.
        </div>
      </Panel>
    );
  }

  const openBar = nearestByTime(payload.bars, row.openTs);
  const closeBar = nearestByTime(payload.bars, row.closeTs);
  const ta = nearestByTime(payload.taFeatures, row.openTs);
  const legs = tradeLegsForLifecycle(row, payload.trades);
  const entryNotional = row.qty * row.entryPrice;
  const exitNotional = row.qty * row.exitPrice;
  const priceWindow = priceWindowForLifecycle(row, payload.bars);
  const openIsBuy = row.side !== "short";
  const tradeChart: ChartConfig = {
    id: `trade-${lifecycleKey(row)}`,
    title: "Trade Price Context",
    subtitle: "open and close on BTC close",
    valueLabel: "BTC close",
    height: 320,
    accent: "primary",
    series: [{ label: "BTC close", points: priceWindow, color: dashboardColors.primary, fill: true }],
    markerMode: "trade",
    markers: [
      { timestamp: row.openTs, label: "Open", color: openIsBuy ? dashboardColors.primary : dashboardColors.adverse, value: row.entryPrice },
      { timestamp: row.closeTs, label: "Close", color: row.pnlTotal >= 0 ? dashboardColors.primaryLight : dashboardColors.adverse, value: row.exitPrice }
    ]
  };
  const matchedSignal =
    row.kind === "directional"
      ? row.side === "short"
        ? ta?.breakoutShort || (ta?.confluenceShort ?? 0) > 0
        : ta?.breakoutLong || (ta?.confluenceLong ?? 0) > 0
      : true;
  const logicSummary =
    row.kind === "directional"
      ? `Directional overlay ${matchedSignal ? "had matching TA support" : "did not have a direct TA trigger in the nearest dumped feature row"} and is only eligible in RISK_ON. Entry regime: ${openBar?.regime ?? "unknown"}.`
      : `Carry core lifecycle opened by the regime-driven delta-neutral hedge policy. It closes on ${row.exitReason || "policy exit"} and rebalances spot/perp exposure.`;

  return (
    <section id="trade-inspector" className="relative scroll-mt-24 overflow-hidden rounded-[var(--radius-lg)] border border-uiBorderMedium bg-uiSurfaceGlassDeep shadow-2xl shadow-black/20">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(7,223,193,0.018),transparent_34%)]" />
      <div className="relative">
        <div className="flex flex-col gap-4 border-b border-uiBorderMedium px-5 py-5 md:flex-row md:items-start md:justify-between">
          <div className="max-w-4xl">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-[20px] font-bold tracking-tight text-uiTextPrimary">Trade Inspector</h2>
              <span className={`rounded-md border border-primary/25 px-3 py-1 font-mono text-[12px] font-semibold uppercase tracking-[0.12em] ${regimeClass(openBar?.regime ?? "")}`}>
              {openBar?.regime ?? "UNKNOWN"}
              </span>
            </div>
            <h3 className="mt-3 text-lg font-medium capitalize text-uiTextPrimary">
              {row.kind === "directional" ? "Directional Overlay" : "Carry Core"} / {row.side}
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-uiTextDim">{logicSummary}</p>
          </div>
          <div className="min-w-[150px] text-left md:text-right">
            <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-uiTextDim">{row.kind} lifecycle</p>
            <p className="mt-3 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-uiTextDim">Total PnL</p>
            <p className={`mt-1 font-mono text-4xl font-bold leading-none ${row.pnlTotal >= 0 ? "text-primary" : "text-adverse"}`}>
              {formatNumber(row.pnlTotal, 2)}
            </p>
            <p className="mt-2 font-mono text-sm text-uiTextDim">{formatPercent(row.navDeltaPct ?? 0)} NAV delta</p>
          </div>
        </div>

        <div className="px-5 py-5">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div>
              <InspectorSectionTitle>Trade Price Context</InspectorSectionTitle>
              <p className="mt-2 text-sm font-semibold text-uiTextDim">Open and close overlaid on BTC close</p>
            </div>
            <span className="font-mono text-xs font-semibold text-uiTextDim">
              {formatDate(row.openTs)} → {formatDate(row.closeTs)}
            </span>
          </div>
          <div className="rounded-[var(--radius-md)] border border-uiBorderMedium bg-[var(--bg-input)] p-4">
            <RenderChart config={tradeChart} framed={false} />
          </div>
        </div>

        <div className="grid border-t border-uiBorderMedium xl:grid-cols-[1fr_0.95fr]">
          <div className="px-5 py-5 xl:border-r xl:border-uiBorderMedium">
            <InspectorSectionTitle>Position</InspectorSectionTitle>
            <dl className="mt-6 grid gap-x-8 gap-y-6 sm:grid-cols-2 xl:grid-cols-4">
              <DetailItem label="Opened" value={formatDateTime(row.openTs)} />
              <DetailItem label="Closed" value={formatDateTime(row.closeTs)} />
              <DetailItem label="Bars Held" value={formatNumber(row.barsHeld, 0)} />
              <DetailItem label="Qty" value={formatCompact(row.qty)} />
              <DetailItem label="Entry" value={`$${formatNumber(row.entryPrice, 2)}`} />
              <DetailItem label="Exit" value={`$${formatNumber(row.exitPrice, 2)}`} />
              <DetailItem label="Entry Notional" value={`$${formatCompact(entryNotional)}`} />
              <DetailItem label="NAV Entry" value={`$${formatNumber(row.navEntry, 2)}`} />
              <DetailItem label="NAV Exit" value={`$${formatNumber(row.navExit, 2)}`} />
              <DetailItem label="Entry Leverage" value={`${formatNumber(openBar?.leverage ?? 0, 3)}x`} />
              <DetailItem label="Close Leverage" value={`${formatNumber(closeBar?.leverage ?? 0, 3)}x`} />
              <DetailItem label="Exit Reason" value={row.exitReason || "-"} />
            </dl>
          </div>
          <div className="px-5 py-5">
            <InspectorSectionTitle>PnL Breakdown</InspectorSectionTitle>
            <dl className="mt-6 grid grid-cols-2 gap-x-8 gap-y-6">
              <DetailItem label="Price" value={formatNumber(row.pnlPrice, 2)} tone={toneFor(row.pnlPrice) === "supportive" ? "supportive" : toneFor(row.pnlPrice) === "adverse" ? "adverse" : undefined} />
              <DetailItem label="Funding" value={formatNumber(row.pnlFunding, 2)} tone={toneFor(row.pnlFunding) === "supportive" ? "supportive" : toneFor(row.pnlFunding) === "adverse" ? "adverse" : undefined} />
              <DetailItem label="Fees" value={formatNumber(row.pnlFees, 2)} tone="adverse" />
              <DetailItem label="Slippage" value={formatNumber(row.pnlSlippage, 2)} tone="adverse" />
            </dl>
          </div>
        </div>

        <div className="border-t border-uiBorderMedium px-5 py-5">
          <InspectorSectionTitle>Signal Context</InspectorSectionTitle>
          <dl className="mt-6 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
            <DetailItem label="Compression" value={ta?.compress ? "Yes" : "No"} />
            <DetailItem label="Breakout Long" value={ta?.breakoutLong ? "Yes" : "No"} />
            <DetailItem label="Breakout Short" value={ta?.breakoutShort ? "Yes" : "No"} />
            <DetailItem label="4H Bias" value={formatNumber(ta?.bias4h ?? 0, 3)} />
            <DetailItem label="Long Confluence" value={formatNumber(ta?.confluenceLong ?? 0, 3)} />
            <DetailItem label="Short Confluence" value={formatNumber(ta?.confluenceShort ?? 0, 3)} />
            <DetailItem label="Nearest Level" value={ta?.nearestLevelKind || "-"} />
            <DetailItem label="Level Distance" value={`${formatNumber(ta?.nearestLevelDistanceAtr ?? 0, 2)} ATR`} />
          </dl>
        </div>

        <div className="border-t border-uiBorderMedium px-5 py-5">
          <div className="mb-3 flex items-center justify-between">
            <InspectorSectionTitle>Matched Execution Legs</InspectorSectionTitle>
            <span className="font-mono text-xs font-semibold text-uiTextDim">{legs.length} legs, exit notional ${formatCompact(exitNotional)}</span>
          </div>
          <DataTable
            columns={["Time", "Leg", "Qty", "Price", "Notional", "Fee", "Slip"]}
            rows={legs.slice(0, 12).map((trade, index) => [
              <span key="time" className="font-mono text-uiTextDim">{formatDateTime(trade.ts)}</span>,
              <span key="leg" className="rounded-md bg-primary/10 px-2 py-1 font-mono text-[11px] font-semibold text-primary">
                {index === 0 ? "Entry" : index === legs.length - 1 ? "Exit" : trade.leg}
              </span>,
              formatCompact(Math.abs(trade.qtyDelta)),
              `$${formatNumber(trade.price, 2)}`,
              `$${formatNumber(Math.abs(trade.notional), 2)}`,
              formatNumber(trade.fee, 2),
              formatNumber(trade.slippage, 2)
            ])}
            emptyLabel="No matched execution legs"
          />
        </div>
      </div>
    </section>
  );
}

export function TradingDashboardClient() {
  const [state, setState] = useState<LoadState>({ status: "loading", data: null, error: null });
  const [runForm, setRunForm] = useState<RunForm>(defaultRunForm);
  const [isRunning, setIsRunning] = useState(false);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [expandedChart, setExpandedChart] = useState<ChartConfig | null>(null);
  const [isExpandedChartLoading, setIsExpandedChartLoading] = useState(false);
  const [selectedLifecycleKey, setSelectedLifecycleKey] = useState<string | null>(null);
  const [pendingLifecycleKey, setPendingLifecycleKey] = useState<string | null>(null);
  const [, startLifecycleTransition] = useTransition();
  const lifecycleLoadTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const expandedChartTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeExpandedChart = useCallback(() => setExpandedChart(null), []);

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

  useEffect(() => {
    return () => {
      if (lifecycleLoadTimer.current) clearTimeout(lifecycleLoadTimer.current);
      if (expandedChartTimer.current) clearTimeout(expandedChartTimer.current);
    };
  }, []);

  const payload = state.data;
  const kpis = useMemo(() => (payload ? buildKpis(payload) : []), [payload]);
  const metrics = useMemo(() => (payload ? metricMap(payload) : new Map<string, number>()), [payload]);
  const selectedLifecycle = useMemo(() => {
    if (!payload?.lifecycles.length || !selectedLifecycleKey) return null;
    return payload.lifecycles.find((row) => lifecycleKey(row) === selectedLifecycleKey) ?? null;
  }, [payload, selectedLifecycleKey]);
  const directionalLifecycles = useMemo(
    () => payload?.lifecycles.filter((row) => row.kind === "directional") ?? [],
    [payload]
  );
  const carryLifecycles = useMemo(
    () => payload?.lifecycles.filter((row) => row.kind === "carry") ?? [],
    [payload]
  );
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
  const priceCandles = useMemo(
    () =>
      payload?.bars.map((bar) => ({
        timestamp: bar.timestamp,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close
      })) ?? [],
    [payload]
  );
  const priceTradeMarkers = useMemo(
    () => (payload ? tradeMarkersForPriceChart(payload.lifecycles) : []),
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
      setSelectedLifecycleKey(null);
      setRunStatus("Run complete. Dashboard updated from out/next-dashboard.");
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Unknown run error");
      setRunStatus(null);
    } finally {
      setIsRunning(false);
    }
  }

  function selectLifecycle(row: LifecycleRow) {
    const key = lifecycleKey(row);
    if (lifecycleLoadTimer.current) clearTimeout(lifecycleLoadTimer.current);
    setPendingLifecycleKey(key);
    setSelectedLifecycleKey(null);
    requestAnimationFrame(() => {
      document.getElementById("trade-inspector")?.scrollIntoView({ behavior: preferredScrollBehavior(), block: "start" });
    });
    lifecycleLoadTimer.current = setTimeout(() => {
      startLifecycleTransition(() => {
        setSelectedLifecycleKey(key);
        setPendingLifecycleKey(null);
      });
    }, 450);
  }

  function expandChart(config: ChartConfig) {
    if (expandedChartTimer.current) clearTimeout(expandedChartTimer.current);
    setExpandedChart(config);
    setIsExpandedChartLoading(true);
    expandedChartTimer.current = setTimeout(() => setIsExpandedChartLoading(false), 320);
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
          { label: "Strategy NAV", points: navSeries, color: dashboardColors.primary, fill: true },
          { label: "Buy & hold NAV", points: buyHoldSeries, color: dashboardColors.textSecondary, dashed: true }
        ]
      },
      ta: {
        id: "ta",
        title: "TA Confluence",
        subtitle: "compression and trigger context",
        valueLabel: "TA confluence",
        height: 255,
        points: compressionSeries,
        accent: "green" as const,
        chartType: "histogram" as const
      },
      price: {
        id: "price",
        title: "BTC Close Price & Directional Executions",
        subtitle: "buy/sell overlays on underlying close",
        valueLabel: "BTC Close (USD)",
        height: 320,
        points: priceSeries,
        candles: priceCandles,
        defaultMode: "candles" as const,
        markers: priceTradeMarkers,
        accent: "white" as const,
        chartType: "candles" as const
      },
      leverage: {
        id: "leverage",
        title: "Leverage",
        subtitle: `realized gross exposure / NAV, effective cap ${formatNumber(configuredEffectiveLeverageCap(runForm), 2)}x`,
        valueLabel: "Realized Leverage",
        height: 320,
        points: leverageSeries,
        accent: "green" as const,
        chartType: "area" as const,
        stepped: true
      },
      exposure: {
        id: "exposure",
        title: "Exposure",
        subtitle: "gross exposure % NAV",
        valueLabel: "Exposure",
        height: 320,
        points: exposureSeries,
        percent: true,
        accent: "amber" as const,
        chartType: "area" as const
      }
    }),
    [buyHoldSeries, compressionSeries, exposureSeries, leverageSeries, navSeries, priceCandles, priceSeries, priceTradeMarkers, runForm]
  );

  if (state.status === "loading") {
    return <DashboardSkeleton />;
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
    <div className="mx-auto flex w-full min-w-0 max-w-[1760px] flex-col gap-5 overflow-x-clip px-5 py-8">
      <Header payload={payload} />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} {...kpi} />
        ))}
      </section>

      <section id="run" className="scroll-mt-24">
        <RunControls
          form={runForm}
          isRunning={isRunning}
          status={runStatus}
          error={runError}
          onChange={(patch) => setRunForm((current) => ({ ...current, ...patch }))}
          onSubmit={runSimulation}
        />
      </section>

      <section id="charts" className="scroll-mt-24 grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <ChartPanel config={chartConfigs.nav} onExpand={expandChart} />
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
                <ExpandButton label="TA Confluence" onClick={() => expandChart(chartConfigs.ta)} />
              </div>
              <RenderChart config={chartConfigs.ta} framed={false} />
            </div>
          </div>
        </Panel>
      </section>

      <section className="grid gap-5">
        <ChartPanel config={chartConfigs.price} onExpand={expandChart} />
        <ChartPanel config={chartConfigs.leverage} onExpand={expandChart} />
        <ChartPanel config={chartConfigs.exposure} onExpand={expandChart} />
      </section>

      <section id="events" className="scroll-mt-24 grid gap-5 xl:grid-cols-2">
        <Panel title="Shadow Events" subtitle="most recent rows">
          <ShadowTable rows={payload.shadow} />
        </Panel>
        <Panel title="Execution Legs" subtitle="spot/perp simulator legs">
          <ExecutionTable rows={payload.trades} />
        </Panel>
      </section>

      <section id="trades" className="scroll-mt-24 grid gap-5 xl:grid-cols-2">
        <LifecycleTable
          title="Directional Overlay Trades"
          rows={directionalLifecycles}
          selectedKey={pendingLifecycleKey ?? (selectedLifecycle ? lifecycleKey(selectedLifecycle) : null)}
          onSelect={selectLifecycle}
        />
        <LifecycleTable
          title="Carry Core Lifecycles"
          rows={carryLifecycles}
          selectedKey={pendingLifecycleKey ?? (selectedLifecycle ? lifecycleKey(selectedLifecycle) : null)}
          onSelect={selectLifecycle}
        />
      </section>
      {pendingLifecycleKey ? (
        <div id="trade-inspector" className="scroll-mt-24">
          <TradeInspectorSkeleton />
        </div>
      ) : selectedLifecycle ? (
        <TradeInspector row={selectedLifecycle} payload={payload} />
      ) : null}
      <footer className="border-t border-uiBorderMedium pt-4 text-right font-mono text-[0.68rem] text-uiTextDim">
        <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center rounded-md transition hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60">
          Charts by TradingView
        </a>
      </footer>
      <ChartModal config={expandedChart} isLoading={isExpandedChartLoading} onClose={closeExpandedChart} />
    </div>
  );
}
