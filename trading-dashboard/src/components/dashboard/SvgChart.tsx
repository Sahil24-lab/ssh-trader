"use client";

import { useId, useMemo, useRef, useState } from "react";
import { formatDate, formatDateTime, formatNumber, formatPercent } from "@/lib/format";

export type ChartPoint = {
  timestamp: string;
  value: number;
};

export type ChartSeries = {
  label: string;
  points: ChartPoint[];
  color?: string;
  dashed?: boolean;
  fill?: boolean;
};

type SvgChartProps = {
  points?: ChartPoint[];
  secondary?: ChartPoint[];
  series?: ChartSeries[];
  height?: number;
  valueLabel?: string;
  percent?: boolean;
  accent?: "primary" | "green" | "amber" | "white";
  framed?: boolean;
};

const colors = {
  primary: "#07DFC1",
  green: "#28c76f",
  amber: "#F0A04B",
  white: "#A9B7C8"
};

const margin = { top: 18, right: 18, bottom: 48, left: 82 };
const width = 1000;

function downsample(points: ChartPoint[], target = 680): ChartPoint[] {
  if (points.length <= target) return points;
  const step = Math.ceil(points.length / target);
  return points.filter((_, index) => index % step === 0 || index === points.length - 1);
}

function sanitize(points: ChartPoint[]): ChartPoint[] {
  return points
    .filter((point) => Number.isFinite(point.value) && Number.isFinite(new Date(point.timestamp).getTime()))
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

function buildPath(
  points: ChartPoint[],
  minY: number,
  maxY: number,
  minT: number,
  maxT: number,
  chartWidth: number,
  chartHeight: number
): string {
  if (points.length === 0) return "";
  const ySpan = Math.max(1, maxY - minY);
  const tSpan = Math.max(1, maxT - minT);
  return points
    .map((point, index) => {
      const t = new Date(point.timestamp).getTime();
      const x = margin.left + ((t - minT) / tSpan) * chartWidth;
      const y = margin.top + chartHeight - ((point.value - minY) / ySpan) * chartHeight;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function valueAt(points: ChartPoint[], targetTime: number): ChartPoint | null {
  if (!points.length) return null;
  let best = points[0];
  let bestDelta = Math.abs(new Date(best.timestamp).getTime() - targetTime);
  for (let index = 1; index < points.length; index += 1) {
    const delta = Math.abs(new Date(points[index].timestamp).getTime() - targetTime);
    if (delta < bestDelta) {
      best = points[index];
      bestDelta = delta;
    }
  }
  return best;
}

function ticks(min: number, max: number, count: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || count <= 1) return [];
  return Array.from({ length: count }, (_, index) => min + ((max - min) * index) / (count - 1));
}

function formatAxisMonth(value: number): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const month = date.toLocaleString(undefined, { month: "short" });
  const year = String(date.getFullYear()).slice(-2);
  return `${month} '${year}`;
}

export function SvgChart({
  points = [],
  secondary,
  series,
  height = 260,
  valueLabel = "Value",
  percent = false,
  accent = "primary",
  framed = true
}: SvgChartProps) {
  const idPrefix = useId().replace(/:/g, "");
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hoverX, setHoverX] = useState<number | null>(null);

  const chartSeries = useMemo<ChartSeries[]>(() => {
    if (series?.length) {
      return series.map((item) => ({ ...item, points: downsample(sanitize(item.points)) }));
    }
    const primary = downsample(sanitize(points));
    const secondaryPoints = downsample(sanitize(secondary ?? []));
    return [
      { label: valueLabel, points: primary, color: colors[accent], fill: true },
      ...(secondaryPoints.length
        ? [{ label: "Secondary", points: secondaryPoints, color: "rgba(239,254,235,0.62)", dashed: true }]
        : [])
    ];
  }, [accent, points, secondary, series, valueLabel]);

  const allPoints = chartSeries.flatMap((item) => item.points);
  const allValues = allPoints.map((point) => point.value);
  const allTimes = allPoints.map((point) => new Date(point.timestamp).getTime());
  const rawMin = Math.min(...allValues);
  const rawMax = Math.max(...allValues);
  const rawMinT = Math.min(...allTimes);
  const rawMaxT = Math.max(...allTimes);
  const yPad = Math.max((rawMax - rawMin) * 0.08, rawMax === rawMin ? Math.abs(rawMax) * 0.05 || 1 : 0);
  const minY = Number.isFinite(rawMin) ? rawMin - yPad : 0;
  const maxY = Number.isFinite(rawMax) ? rawMax + yPad : 1;
  const minT = Number.isFinite(rawMinT) ? rawMinT : Date.now();
  const maxT = Number.isFinite(rawMaxT) ? rawMaxT : minT + 1;
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const fmt = percent ? formatPercent : (value: number) => formatNumber(value, Math.abs(value) < 10 ? 3 : 2);
  const yTicks = ticks(minY, maxY, 5).reverse();
  const xTicks = ticks(minT, maxT, 6);
  const hoverTime =
    hoverX === null ? null : minT + ((Math.max(margin.left, Math.min(width - margin.right, hoverX)) - margin.left) / chartWidth) * (maxT - minT);
  const hoverValues =
    hoverTime === null
      ? []
      : chartSeries
          .map((item) => ({ series: item, point: valueAt(item.points, hoverTime) }))
          .filter((item): item is { series: ChartSeries; point: ChartPoint } => item.point !== null);
  const hoverPointTime = hoverValues[0] ? new Date(hoverValues[0].point.timestamp).getTime() : hoverTime;
  const hoverLineX =
    hoverPointTime === null ? null : margin.left + ((hoverPointTime - minT) / Math.max(1, maxT - minT)) * chartWidth;

  return (
    <div className={`relative ${framed ? "rounded-[10px] border border-uiBorderMedium bg-[#06111f] p-3" : ""}`}>
      <div className="mb-2 flex items-center justify-between gap-4 text-[12px] text-uiTextDim">
        <span>{valueLabel}</span>
        <span>
          {Number.isFinite(minT) ? formatDate(new Date(minT).toISOString()) : "-"} →{" "}
          {Number.isFinite(maxT) ? formatDate(new Date(maxT).toISOString()) : "-"}
        </span>
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        className="h-full w-full overflow-visible"
        onMouseMove={(event) => {
          const rect = svgRef.current?.getBoundingClientRect();
          if (!rect) return;
          setHoverX(((event.clientX - rect.left) / rect.width) * width);
        }}
        onMouseLeave={() => setHoverX(null)}
      >
        <defs>
          {chartSeries.map((item, index) => (
            <linearGradient key={`${item.label}-${index}`} id={`${idPrefix}-fill-${index}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={item.color ?? colors[accent]} stopOpacity="0.20" />
              <stop offset="100%" stopColor={item.color ?? colors[accent]} stopOpacity="0.02" />
            </linearGradient>
          ))}
        </defs>

        <rect
          x={margin.left}
          y={margin.top}
          width={chartWidth}
          height={chartHeight}
          fill="rgba(3,13,24,0.32)"
          rx="6"
        />

        {yTicks.map((tick) => {
          const y = margin.top + chartHeight - ((tick - minY) / Math.max(1, maxY - minY)) * chartHeight;
          return (
            <g key={tick}>
              <line x1={margin.left} x2={width - margin.right} y1={y} y2={y} stroke="rgba(7,223,193,0.10)" />
              <text x={margin.left - 12} y={y + 4} fill="#8EA0B8" fontSize="13" textAnchor="end">
                {fmt(tick)}
              </text>
            </g>
          );
        })}

        {xTicks.map((tick, index) => {
          const x = margin.left + ((tick - minT) / Math.max(1, maxT - minT)) * chartWidth;
          const textAnchor = index === 0 ? "start" : index === xTicks.length - 1 ? "end" : "middle";
          return (
            <g key={tick}>
              <line x1={x} x2={x} y1={margin.top} y2={margin.top + chartHeight} stroke="rgba(7,223,193,0.045)" />
              <text x={x} y={height - 14} fill="#8EA0B8" fontSize="12" textAnchor={textAnchor}>
                {formatAxisMonth(tick)}
              </text>
            </g>
          );
        })}

        {chartSeries.map((item, index) => {
          const path = buildPath(item.points, minY, maxY, minT, maxT, chartWidth, chartHeight);
          if (!path) return null;
          const color = item.color ?? colors[accent];
          return (
            <g key={`${item.label}-${index}`}>
              {item.fill ? (
                <path
                  d={`${path} L ${width - margin.right} ${margin.top + chartHeight} L ${margin.left} ${margin.top + chartHeight} Z`}
                  fill={`url(#${idPrefix}-fill-${index})`}
                />
              ) : null}
              <path
                d={path}
                fill="none"
                stroke={color}
                strokeDasharray={item.dashed ? "6 5" : undefined}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={item.dashed ? "1.8" : "2.2"}
              />
            </g>
          );
        })}

        {hoverLineX !== null ? (
          <g>
            <line
              x1={hoverLineX}
              x2={hoverLineX}
              y1={margin.top}
              y2={margin.top + chartHeight}
              stroke="rgba(239,254,235,0.50)"
              strokeWidth="1"
            />
            {hoverValues.map(({ series: item, point }) => {
              const y = margin.top + chartHeight - ((point.value - minY) / Math.max(1, maxY - minY)) * chartHeight;
              return <circle key={item.label} cx={hoverLineX} cy={y} r="4" fill={item.color ?? colors[accent]} stroke="#06111f" strokeWidth="2" />;
            })}
          </g>
        ) : null}
      </svg>

      {hoverValues.length && hoverLineX !== null ? (
        <div
          className="pointer-events-none absolute top-14 z-20 min-w-[210px] rounded-[10px] border border-uiBorderStrong bg-[#030b14]/95 p-3 shadow-2xl"
          style={{ left: `${Math.min(78, Math.max(2, (hoverLineX / width) * 100 - 10))}%` }}
        >
          <div className="mb-2 font-mono text-[12px] text-uiTextDim">{formatDateTime(hoverValues[0].point.timestamp)}</div>
          <div className="space-y-1.5">
            {hoverValues.map(({ series: item, point }) => (
              <div key={item.label} className="flex items-center justify-between gap-4 text-[12px]">
                <span className="flex items-center gap-2 text-uiTextDim">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color ?? colors[accent] }} />
                  {item.label}
                </span>
                <span className="font-mono font-semibold text-uiTextPrimary">{fmt(point.value)}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {chartSeries.length > 1 ? (
        <div className="mt-2 flex flex-wrap gap-4 text-[12px] font-semibold text-uiTextDim">
          {chartSeries.map((item, index) => (
            <span key={`${item.label}-${index}`} className="inline-flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color ?? colors[accent] }} />
              {item.label}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
