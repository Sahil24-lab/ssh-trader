"use client";

import { memo, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import {
  AreaSeries,
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  LineType,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp
} from "lightweight-charts";
import { formatDate } from "@/lib/format";
import { dashboardColors } from "@/lib/dashboard/theme";

export type ChartPoint = {
  timestamp: string;
  value: number;
};

export type CandlePoint = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type ChartSeries = {
  label: string;
  points: ChartPoint[];
  color?: string;
  dashed?: boolean;
  fill?: boolean;
};

export type ChartMarker = {
  timestamp: string;
  label: string;
  color?: string;
  value?: number;
};

type SvgChartProps = {
  points?: ChartPoint[];
  secondary?: ChartPoint[];
  series?: ChartSeries[];
  candles?: CandlePoint[];
  defaultMode?: "line" | "candles";
  markers?: ChartMarker[];
  markerMode?: "native" | "trade";
  height?: number;
  valueLabel?: string;
  percent?: boolean;
  accent?: "primary" | "green" | "amber" | "white";
  framed?: boolean;
  chartType?: "line" | "area" | "candles" | "histogram";
  stepped?: boolean;
};

const colors = {
  primary: dashboardColors.primary,
  green: dashboardColors.primary,
  amber: dashboardColors.warning,
  white: dashboardColors.textSecondary
};

const chartTheme = {
  layout: {
    background: { type: ColorType.Solid, color: "transparent" },
    textColor: dashboardColors.textMuted,
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 10
  },
  grid: {
    vertLines: { color: dashboardColors.primaryGrid },
    horzLines: { color: dashboardColors.primaryGrid }
  },
  crosshair: {
    mode: 0,
    vertLine: {
      color: dashboardColors.primaryGuide,
      width: 1 as const,
      style: LineStyle.Dashed,
      labelBackgroundColor: dashboardColors.chartLabelBackground
    },
    horzLine: {
      color: dashboardColors.primaryGuide,
      width: 1 as const,
      style: LineStyle.Dashed,
      labelBackgroundColor: dashboardColors.chartLabelBackground
    }
  },
  timeScale: {
    borderColor: dashboardColors.primaryBorder,
    timeVisible: true,
    secondsVisible: false
  },
  rightPriceScale: {
    borderColor: dashboardColors.primaryBorder
  },
  handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
  handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true }
};

const EMPTY_POINTS: ChartPoint[] = [];
const EMPTY_CANDLES: CandlePoint[] = [];
const EMPTY_MARKERS: ChartMarker[] = [];

function colorWithAlpha(color: string, alpha: number): string {
  const clamped = Math.max(0, Math.min(1, alpha));
  if (color.startsWith("#") && color.length === 7) {
    return `${color}${Math.round(clamped * 255)
      .toString(16)
      .padStart(2, "0")}`;
  }
  const rgba = color.match(/^rgba?\(([^)]+)\)$/);
  if (!rgba) return color;
  const [r, g, b] = rgba[1].split(",").map((part) => part.trim());
  return `rgba(${r}, ${g}, ${b}, ${clamped})`;
}

function toTime(timestamp: string): UTCTimestamp {
  return Math.floor(new Date(timestamp).getTime() / 1000) as UTCTimestamp;
}

function sanitize(points: ChartPoint[]): ChartPoint[] {
  return points.filter((point) => Number.isFinite(point.value) && Number.isFinite(new Date(point.timestamp).getTime()));
}

function sanitizeCandles(candles: CandlePoint[]): CandlePoint[] {
  return candles.filter(
    (point) =>
      [point.open, point.high, point.low, point.close].every(Number.isFinite) &&
      Number.isFinite(new Date(point.timestamp).getTime())
  );
}

function asLineData(points: ChartPoint[]) {
  return sanitize(points).map((point) => ({ time: toTime(point.timestamp), value: point.value }));
}

function asCandleData(candles: CandlePoint[]) {
  return sanitizeCandles(candles).map((point) => ({
    time: toTime(point.timestamp),
    open: point.open,
    high: point.high,
    low: point.low,
    close: point.close
  }));
}

function buildDefaultSeries(
  points: ChartPoint[],
  secondary: ChartPoint[] | undefined,
  valueLabel: string,
  accent: keyof typeof colors
): ChartSeries[] {
  const primary = sanitize(points);
  const secondaryPoints = sanitize(secondary ?? []);
  return [
    { label: valueLabel, points: primary, color: colors[accent], fill: true },
    ...(secondaryPoints.length
      ? [{ label: "Secondary", points: secondaryPoints, color: dashboardColors.textSecondary, dashed: true }]
      : [])
  ];
}

function dataBounds(points: ChartPoint[], candles: CandlePoint[]) {
  const times = [
    ...points.map((point) => new Date(point.timestamp).getTime()),
    ...candles.map((point) => new Date(point.timestamp).getTime())
  ].filter(Number.isFinite);
  return {
    first: times.length ? Math.min(...times) : null,
    last: times.length ? Math.max(...times) : null
  };
}

function rangeFrom(last: number, first: number, range: "1M" | "3M" | "6M" | "ALL") {
  if (range === "ALL") return { from: Math.floor(first / 1000) as UTCTimestamp, to: Math.floor(last / 1000) as UTCTimestamp };
  const days = range === "1M" ? 31 : range === "3M" ? 93 : 186;
  return {
    from: Math.floor(Math.max(first, last - days * 24 * 60 * 60 * 1000) / 1000) as UTCTimestamp,
    to: Math.floor(last / 1000) as UTCTimestamp
  };
}

function markerShape(label: string) {
  const normalized = label.toLowerCase();
  if (normalized.includes("buy") || normalized.includes("open")) return "arrowUp" as const;
  if (normalized.includes("sell") || normalized.includes("close")) return "arrowDown" as const;
  return "circle" as const;
}

function markerPosition(label: string) {
  const normalized = label.toLowerCase();
  return normalized.includes("buy") || normalized.includes("open") ? "belowBar" : "aboveBar";
}

function valueForMarker(marker: ChartMarker, chartSeries: ChartSeries[]): number | null {
  if (Number.isFinite(marker.value)) return marker.value ?? null;
  const primaryPoints = chartSeries[0]?.points ?? [];
  if (!primaryPoints.length) return null;
  const markerTime = timeMs(marker.timestamp);
  const nearest = primaryPoints.reduce<ChartPoint | null>((best, point) => {
    if (!best) return point;
    return Math.abs(timeMs(point.timestamp) - markerTime) < Math.abs(timeMs(best.timestamp) - markerTime) ? point : best;
  }, null);
  return nearest?.value ?? null;
}

function timeMs(timestamp: string): number {
  const parsed = new Date(timestamp).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
}

function overlaysEqual(
  left: Array<{ label: string; color: string; x: number; y: number }>,
  right: Array<{ label: string; color: string; x: number; y: number }>
) {
  if (left === right) return true;
  if (left.length !== right.length) return false;
  for (let index = 0; index < left.length; index += 1) {
    const a = left[index];
    const b = right[index];
    if (!a || !b) return false;
    if (a.label !== b.label || a.color !== b.color || a.x !== b.x || a.y !== b.y) return false;
  }
  return true;
}

function SvgChartImpl({
  points = EMPTY_POINTS,
  secondary,
  series,
  candles = EMPTY_CANDLES,
  defaultMode = "line",
  markers = EMPTY_MARKERS,
  markerMode = "native",
  height = 260,
  valueLabel = "Value",
  percent = false,
  accent = "primary",
  framed = true,
  chartType = "area",
  stepped = false
}: SvgChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const primarySeriesRef = useRef<{ priceToCoordinate?: (price: number) => number | null } | null>(null);
  const [shouldRenderChart, setShouldRenderChart] = useState(false);
  const [tradeMarkerOverlays, setTradeMarkerOverlays] = useState<Array<{ label: string; color: string; x: number; y: number }>>([]);
  const [mode, setMode] = useState<"line" | "candles">(candles.length ? defaultMode : "line");
  const [range, setRange] = useState<"1M" | "3M" | "6M" | "ALL">("ALL");
  const showInlineControls = height >= 220;

  const chartSeries = useMemo(
    () => (series?.length ? series.map((item) => ({ ...item, points: sanitize(item.points) })) : buildDefaultSeries(points, secondary, valueLabel, accent)),
    [accent, points, secondary, series, valueLabel]
  );
  const candleData = useMemo(() => asCandleData(candles), [candles]);
  const lineData = useMemo(() => asLineData(points), [points]);
  const allPoints = useMemo(() => chartSeries.flatMap((item) => item.points), [chartSeries]);
  const bounds = useMemo(() => dataBounds(allPoints.length ? allPoints : points, candles), [allPoints, candles, points]);
  const dateLabel =
    bounds.first && bounds.last
      ? `${formatDate(new Date(bounds.first).toISOString())} → ${formatDate(new Date(bounds.last).toISOString())}`
      : "-";

  useEffect(() => {
    setMode(candles.length ? defaultMode : "line");
    setRange("ALL");
  }, [candles.length, defaultMode]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || shouldRenderChart) return;
    let idleId: number | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const scheduleRender = () => {
      const render = () => setShouldRenderChart(true);
      if ("requestIdleCallback" in window) {
        idleId = window.requestIdleCallback(render, { timeout: 900 });
      } else {
        timeoutId = setTimeout(render, 120);
      }
    };
    if (typeof IntersectionObserver === "undefined") {
      scheduleRender();
      return () => {
        if (idleId !== null) window.cancelIdleCallback(idleId);
        if (timeoutId) clearTimeout(timeoutId);
      };
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          scheduleRender();
          observer.disconnect();
        }
      },
      { rootMargin: "180px 0px" }
    );
    observer.observe(container);
    return () => {
      observer.disconnect();
      if (idleId !== null) window.cancelIdleCallback(idleId);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [shouldRenderChart]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !shouldRenderChart) return;

    const chart = createChart(container, {
      ...chartTheme,
      autoSize: true,
      height,
      localization: {
        priceFormatter: (price: number) => (percent ? `${(price * 100).toFixed(2)}%` : price.toLocaleString(undefined, { maximumFractionDigits: Math.abs(price) < 10 ? 3 : 2 }))
      }
    });
    chartRef.current = chart;
    primarySeriesRef.current = null;
    const markerItems: SeriesMarker<Time>[] = markers.map((marker) => ({
      time: toTime(marker.timestamp),
      position: markerPosition(marker.label),
      color: marker.color ?? colors.primary,
      shape: markerMode === "trade" ? "circle" : markerShape(marker.label),
      text: markerMode === "trade" ? "" : marker.label,
      size: markerMode === "trade" ? 0.72 : 1
    }));

    if (chartType === "histogram") {
      const histogram = chart.addSeries(HistogramSeries, {
        color: colors[accent],
        priceLineVisible: false
      });
      histogram.setData(asLineData(points));
      primarySeriesRef.current = histogram;
    } else if (candles.length) {
      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: colors.primary,
        downColor: dashboardColors.adverse,
        borderUpColor: colors.primary,
        borderDownColor: dashboardColors.adverse,
        wickUpColor: colors.primary,
        wickDownColor: dashboardColors.adverse,
        priceLineVisible: false,
        visible: mode === "candles"
      });
      candleSeries.setData(candleData);
      primarySeriesRef.current = candleSeries;

      const closeSeries = chart.addSeries(LineSeries, {
        color: colors.primary,
        lineWidth: 2,
        priceLineVisible: false,
        visible: mode === "line"
      });
      closeSeries.setData(lineData);

      createSeriesMarkers(candleSeries, markerItems);
      createSeriesMarkers(closeSeries, markerItems);
    } else {
      chartSeries.forEach((item, index) => {
        const data = asLineData(item.points);
        const color = item.color ?? colors[accent];
        if (index === 0 && (item.fill || chartType === "area")) {
          const area = chart.addSeries(AreaSeries, {
            topColor: colorWithAlpha(color, accent === "amber" ? 0.12 : 0.09),
            bottomColor: colorWithAlpha(color, 0),
            lineColor: color,
            lineWidth: index === 0 ? (markerMode === "trade" ? 1 : 2) : 1,
            lineType: stepped ? LineType.WithSteps : LineType.Simple,
            priceLineVisible: false
          });
          area.setData(data);
          if (index === 0) {
            primarySeriesRef.current = area;
          }
          if (index === 0 && markerItems.length) {
            createSeriesMarkers(area, markerItems);
          }
        } else {
          const line = chart.addSeries(LineSeries, {
            color,
            lineWidth: item.dashed || markerMode === "trade" ? 1 : 2,
            lineStyle: item.dashed ? LineStyle.Dashed : LineStyle.Solid,
            lineType: stepped ? LineType.WithSteps : LineType.Simple,
            priceLineVisible: false
          });
          line.setData(data);
          if (index === 0) {
            primarySeriesRef.current = line;
          }
          if (index === 0 && markerItems.length) {
            createSeriesMarkers(line, markerItems);
          }
        }
      });
    }

    chart.timeScale().fitContent();

    const updateTradeOverlays = () => {
      if (markerMode !== "trade" || !primarySeriesRef.current) {
        setTradeMarkerOverlays((previous) => (previous.length ? [] : previous));
        return;
      }

      const next = markers.flatMap((marker) => {
        const x = chart.timeScale().timeToCoordinate(toTime(marker.timestamp));
        const value = valueForMarker(marker, chartSeries);
        const y = value === null ? null : primarySeriesRef.current?.priceToCoordinate?.(value);
        if (x === null || y === null || typeof y !== "number") return [];
        return [{ label: marker.label, color: marker.color ?? colors.primary, x, y }];
      });
      setTradeMarkerOverlays((previous) => (overlaysEqual(previous, next) ? previous : next));
    };

    updateTradeOverlays();
    chart.timeScale().subscribeVisibleLogicalRangeChange(updateTradeOverlays);

    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(updateTradeOverlays);
      chart.remove();
      chartRef.current = null;
      primarySeriesRef.current = null;
    };
  }, [accent, bounds.first, bounds.last, candleData, candles.length, chartSeries, chartType, height, lineData, markerMode, markers, mode, percent, points, shouldRenderChart, stepped]);

  useEffect(() => {
    if (!chartRef.current || !bounds.first || !bounds.last) return;
    chartRef.current.timeScale().setVisibleRange(rangeFrom(bounds.last, bounds.first, range));
  }, [bounds.first, bounds.last, range]);

  function resetChart() {
    setRange("ALL");
    chartRef.current?.timeScale().fitContent();
  }

  function zoomChart(multiplier: number) {
    const timeScale = chartRef.current?.timeScale();
    const logicalRange = timeScale?.getVisibleLogicalRange();
    if (!timeScale || !logicalRange) return;
    const center = (logicalRange.from + logicalRange.to) / 2;
    const halfSpan = Math.max(4, ((logicalRange.to - logicalRange.from) * multiplier) / 2);
    setRange("ALL");
    timeScale.setVisibleLogicalRange({ from: center - halfSpan, to: center + halfSpan });
  }

  function panChart(direction: -1 | 1) {
    const timeScale = chartRef.current?.timeScale();
    const logicalRange = timeScale?.getVisibleLogicalRange();
    if (!timeScale || !logicalRange) return;
    const step = Math.max(4, (logicalRange.to - logicalRange.from) * 0.28);
    setRange("ALL");
    timeScale.setVisibleLogicalRange({ from: logicalRange.from + step * direction, to: logicalRange.to + step * direction });
  }

  return (
    <div className={`relative ${framed ? "rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-[var(--space-md)]" : ""}`}>
      <div className="mb-[var(--space-sm)] flex flex-wrap items-center justify-between gap-[var(--space-sm)] font-mono text-[0.68rem] text-[var(--text-muted)]">
        <span>{valueLabel}</span>
        <div className="flex flex-wrap items-center justify-end gap-[var(--space-sm)]">
          {candles.length ? (
            <div className="flex rounded-[var(--radius-sm)] border border-[var(--border-default)] bg-[var(--bg-input)] p-0.5">
              {(["candles", "line"] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setMode(item)}
                  aria-pressed={mode === item}
                  className={`min-h-11 min-w-11 rounded px-2 py-1 text-[0.66rem] font-bold capitalize transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] ${
                    mode === item ? "bg-[var(--primary)] text-[var(--bg-base)]" : "text-[var(--text-muted)] hover:text-[var(--primary)]"
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
          ) : null}
          <div className="flex rounded-[var(--radius-sm)] border border-[var(--border-default)] bg-[var(--bg-input)] p-0.5">
            {(["1M", "3M", "6M", "ALL"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setRange(item)}
                aria-pressed={range === item}
                className={`min-h-11 min-w-11 rounded px-2 py-1 text-[0.66rem] font-bold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] ${
                  range === item ? "bg-[var(--primary-dim)] text-[var(--primary)]" : "text-[var(--text-muted)] hover:text-[var(--primary)]"
                }`}
              >
                {item}
              </button>
            ))}
          </div>
          <span className="text-left sm:min-w-[150px] sm:text-right">{dateLabel}</span>
        </div>
      </div>
      <div className="group/chart relative">
        <div ref={containerRef} style={{ height }} className="w-full">
          {!shouldRenderChart ? <div className="dashboard-skeleton h-full w-full rounded-[var(--radius-sm)] opacity-60" /> : null}
        </div>
        {markerMode === "trade"
          ? tradeMarkerOverlays.map((marker) => (
              <div key={`${marker.label}-${marker.x}`} className="pointer-events-none absolute inset-y-0 left-0 z-10">
                <span
                  className="absolute top-7 h-[calc(100%-48px)] border-l border-dashed"
                  style={{ left: marker.x, borderColor: colorWithAlpha(marker.color, 0.58) }}
                />
                <span
                  className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--bg-input)]"
                  style={{ left: marker.x, top: marker.y, backgroundColor: marker.color }}
                />
                <span
                  className="absolute -translate-x-1/2 rounded px-1.5 py-0.5 font-display text-[13px] font-semibold leading-none tracking-[-0.01em]"
                  style={{
                    left: marker.x,
                    top: Math.max(28, marker.y - 24),
                    color: marker.color,
                    backgroundColor: colorWithAlpha(dashboardColors.inputBackground, 0.82)
                  }}
                >
                  {marker.label}
                </span>
              </div>
            ))
          : null}
        {showInlineControls ? (
          <div
            className="pointer-events-none absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-1.5 opacity-0 transition duration-150 group-hover/chart:opacity-100 group-focus-within/chart:opacity-100"
            aria-label="Chart navigation controls"
          >
            <IconChartButton label="Zoom out" onClick={() => zoomChart(1.8)} icon={<ZoomOut size={15} strokeWidth={2.3} />} />
            <IconChartButton label="Zoom in" onClick={() => zoomChart(0.55)} icon={<ZoomIn size={15} strokeWidth={2.3} />} />
            <IconChartButton label="Pan left" onClick={() => panChart(-1)} icon={<ChevronLeft size={17} strokeWidth={2.5} />} />
            <IconChartButton label="Pan right" onClick={() => panChart(1)} icon={<ChevronRight size={17} strokeWidth={2.5} />} />
            <IconChartButton label="Fit full range" onClick={resetChart} icon={<RotateCcw size={15} strokeWidth={2.3} />} />
          </div>
        ) : null}
      </div>
      {chartSeries.length > 1 ? (
        <div className="mt-[var(--space-sm)] flex flex-wrap gap-[var(--space-md)] font-mono text-[0.7rem] font-semibold text-[var(--text-muted)]">
          {chartSeries.map((item, index) => (
            <span key={`${item.label}-${index}`} className="inline-flex items-center gap-[var(--space-sm)]">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color ?? colors[accent] }} />
              {item.label}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export const SvgChart = memo(SvgChartImpl);

function IconChartButton({ label, icon, onClick }: { label: string; icon: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="pointer-events-auto grid h-11 w-11 place-items-center rounded-full border border-[var(--border-strong)] bg-[var(--bg-input)] text-[var(--text-secondary)] shadow-[0_4px_8px_rgba(0,0,0,0.35)] transition hover:border-[var(--primary)] hover:bg-[var(--primary-dim)] hover:text-[var(--primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
      aria-label={label}
      title={label}
    >
      {icon}
    </button>
  );
}
