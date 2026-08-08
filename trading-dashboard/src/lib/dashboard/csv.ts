import { readFile } from "node:fs/promises";
import path from "node:path";
import {
  BarRow,
  DashboardPayload,
  LifecycleRow,
  MetricRow,
  ShadowRow,
  TaFeatureRow,
  TradeRow
} from "@/lib/dashboard/types";

export const ROOT_DIR = path.resolve(process.cwd(), "..");

export type DashboardCsvPaths = {
  bars: string;
  metrics: string;
  trades: string;
  lifecycles: string;
  shadow: string;
  taFeatures: string;
};

export const DEFAULT_DASHBOARD_CSV_PATHS: DashboardCsvPaths = {
  bars: "out/bars.csv",
  metrics: "out/metrics.csv",
  trades: "out/trades.csv",
  lifecycles: "out/lifecycle.csv",
  shadow: "out/shadow_log.csv",
  taFeatures: "out/ta_features.csv"
};

const DEFAULT_SOURCE_CSV_PATH = "data/hyperliquid_btc_1h.csv";
const MAX_CHART_POINTS = 800;

function splitCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let quoted = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];

    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      quoted = !quoted;
      continue;
    }

    if (char === "," && !quoted) {
      values.push(current);
      current = "";
      continue;
    }

    current += char;
  }

  values.push(current);
  return values;
}

async function readCsv(relativePath: string): Promise<Record<string, string>[]> {
  const filePath = path.join(ROOT_DIR, relativePath);
  const text = await readFile(filePath, "utf8");
  const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length === 0) return [];

  const headers = splitCsvLine(lines[0]).map((header) => header.trim());
  return lines.slice(1).map((line) => {
    const parts = splitCsvLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, parts[index] ?? ""]));
  });
}

function num(value: string | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function maybeNum(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function bool(value: string | undefined): boolean {
  return value === "1" || value?.toLowerCase() === "true";
}

function mapBars(rows: Record<string, string>[], sourceRows: Record<string, string>[] = []): BarRow[] {
  const sourceByTimestamp = new Map(sourceRows.map((row) => [row.timestamp ?? "", row]));
  return rows.map((row) => ({
    timestamp: row.timestamp ?? "",
    open: num(row.open) || num(sourceByTimestamp.get(row.timestamp ?? "")?.open) || num(row.price),
    high: num(row.high) || num(sourceByTimestamp.get(row.timestamp ?? "")?.high) || num(row.price),
    low: num(row.low) || num(sourceByTimestamp.get(row.timestamp ?? "")?.low) || num(row.price),
    close: num(row.close) || num(sourceByTimestamp.get(row.timestamp ?? "")?.close) || num(row.price),
    price: num(row.price),
    nav: num(row.nav),
    regime: row.regime ?? "",
    carryNotional: num(row.carry_notional),
    directionalNotional: num(row.directional_notional),
    grossExposure: num(row.gross_exposure),
    leverage: num(row.leverage),
    pnlPrice: num(row.pnl_price),
    pnlFunding: num(row.pnl_funding),
    pnlFees: num(row.pnl_fees),
    pnlSlippage: num(row.pnl_slippage),
    killSwitchActive: bool(row.kill_switch_active)
  }));
}

function mapMetrics(rows: Record<string, string>[]): MetricRow[] {
  return rows.map((row) => ({
    metric: row.metric ?? "",
    value: num(row.value)
  }));
}

function mapTrades(rows: Record<string, string>[]): TradeRow[] {
  return rows.map((row) => ({
    ts: row.ts ?? "",
    leg: row.leg ?? "",
    source: row.source ?? "",
    qtyDelta: num(row.qty_delta),
    price: num(row.price),
    notional: num(row.notional),
    fee: num(row.fee),
    slippage: num(row.slippage)
  }));
}

function mapLifecycles(rows: Record<string, string>[]): LifecycleRow[] {
  return rows.map((row) => ({
    openTs: row.open_ts ?? "",
    closeTs: row.close_ts ?? "",
    kind: row.kind ?? "",
    side: row.side ?? "",
    qty: num(row.qty),
    entryPrice: num(row.entry_price),
    exitPrice: num(row.exit_price),
    navEntry: num(row.nav_entry),
    navExit: num(row.nav_exit),
    navDelta: num(row.nav_delta),
    navDeltaPct: maybeNum(row.nav_delta_pct),
    pnlPrice: num(row.pnl_price),
    pnlFunding: num(row.pnl_funding),
    pnlFees: num(row.pnl_fees),
    pnlSlippage: num(row.pnl_slippage),
    pnlTotal: num(row.pnl_total),
    barsHeld: num(row.bars_held),
    exitReason: row.exit_reason ?? ""
  }));
}

function mapShadow(rows: Record<string, string>[]): ShadowRow[] {
  return rows.map((row) => ({
    timestamp: row.timestamp ?? "",
    regime: row.regime ?? "",
    intendedOrder: row.intended_order ?? "",
    hypotheticalFill: row.hypothetical_fill ?? "",
    slippageEstimateBps: num(row.slippage_estimate_bps),
    skipped: bool(row.skipped),
    reason: row.reason ?? "",
    routeHint: row.route_hint ?? ""
  }));
}

function mapTaFeatures(rows: Record<string, string>[]): TaFeatureRow[] {
  return rows.map((row) => ({
    timestamp: row.timestamp ?? "",
    close: num(row.close),
    compress: bool(row.compress),
    breakoutLong: bool(row.breakout_long),
    breakoutShort: bool(row.breakout_short),
    confluenceLong: maybeNum(row.confluence_long),
    confluenceShort: maybeNum(row.confluence_short),
    nearestLevelKind: row.nearest_level_kind ?? "",
    nearestLevelDistanceAtr: maybeNum(row.nearest_level_distance_atr),
    bias4h: maybeNum(row.bias_4h)
  }));
}

function sampleTimeSeries<T>(
  rows: T[],
  timestampFor: (row: T) => string,
  requiredTimestamps: ReadonlySet<string> = new Set()
): T[] {
  if (rows.length <= MAX_CHART_POINTS) return rows;

  const selectedIndexes = new Set<number>([0, rows.length - 1]);
  const stride = (rows.length - 1) / (MAX_CHART_POINTS - 1);
  for (let point = 0; point < MAX_CHART_POINTS; point += 1) {
    selectedIndexes.add(Math.round(point * stride));
  }

  rows.forEach((row, index) => {
    if (requiredTimestamps.has(timestampFor(row))) selectedIndexes.add(index);
  });

  return rows.filter((_, index) => selectedIndexes.has(index));
}

export async function buildDashboardPayload(
  paths: DashboardCsvPaths = DEFAULT_DASHBOARD_CSV_PATHS,
  sourceCsvPath = DEFAULT_SOURCE_CSV_PATH
): Promise<DashboardPayload> {
  const sourceCsv = path.isAbsolute(sourceCsvPath) ? path.relative(ROOT_DIR, sourceCsvPath) : sourceCsvPath;
  const [bars, sourceBars, metrics, trades, lifecycles, shadow, taFeatures] = await Promise.all([
    readCsv(paths.bars),
    readCsv(sourceCsv).catch(() => []),
    readCsv(paths.metrics),
    readCsv(paths.trades),
    readCsv(paths.lifecycles),
    readCsv(paths.shadow),
    readCsv(paths.taFeatures)
  ]);

  const mappedBars = mapBars(bars, sourceBars);
  const mappedLifecycles = mapLifecycles(lifecycles);
  const lifecycleTimestamps = new Set(
    mappedLifecycles.flatMap((row) => [row.openTs, row.closeTs]).filter(Boolean)
  );
  const mappedTaFeatures = mapTaFeatures(taFeatures);
  const sampledBars = sampleTimeSeries(mappedBars, (row) => row.timestamp, lifecycleTimestamps);
  const sampledTaFeatures = sampleTimeSeries(mappedTaFeatures, (row) => row.timestamp);

  return {
    generatedAtUtc: new Date().toISOString(),
    sampling: {
      barsOriginalCount: mappedBars.length,
      barsReturnedCount: sampledBars.length,
      taFeaturesOriginalCount: mappedTaFeatures.length,
      taFeaturesReturnedCount: sampledTaFeatures.length
    },
    bars: sampledBars,
    metrics: mapMetrics(metrics),
    trades: mapTrades(trades),
    lifecycles: mappedLifecycles,
    shadow: mapShadow(shadow).slice(-250),
    taFeatures: sampledTaFeatures
  };
}
