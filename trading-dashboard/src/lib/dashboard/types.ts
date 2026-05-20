export type BarRow = {
  timestamp: string;
  price: number;
  nav: number;
  regime: string;
  carryNotional: number;
  directionalNotional: number;
  grossExposure: number;
  leverage: number;
  pnlPrice: number;
  pnlFunding: number;
  pnlFees: number;
  pnlSlippage: number;
  killSwitchActive: boolean;
};

export type MetricRow = {
  metric: string;
  value: number;
};

export type TradeRow = {
  ts: string;
  leg: string;
  source: string;
  qtyDelta: number;
  price: number;
  notional: number;
  fee: number;
  slippage: number;
};

export type LifecycleRow = {
  openTs: string;
  closeTs: string;
  kind: string;
  side: string;
  qty: number;
  entryPrice: number;
  exitPrice: number;
  navEntry: number;
  navExit: number;
  navDelta: number;
  navDeltaPct: number | null;
  pnlPrice: number;
  pnlFunding: number;
  pnlFees: number;
  pnlSlippage: number;
  pnlTotal: number;
  barsHeld: number;
  exitReason: string;
};

export type ShadowRow = {
  timestamp: string;
  regime: string;
  intendedOrder: string;
  hypotheticalFill: string;
  slippageEstimateBps: number;
  skipped: boolean;
  reason: string;
  routeHint: string;
};

export type TaFeatureRow = {
  timestamp: string;
  close: number;
  compress: boolean;
  breakoutLong: boolean;
  breakoutShort: boolean;
  confluenceLong: number | null;
  confluenceShort: number | null;
  nearestLevelKind: string;
  nearestLevelDistanceAtr: number | null;
  bias4h: number | null;
};

export type DashboardPayload = {
  generatedAtUtc: string;
  bars: BarRow[];
  metrics: MetricRow[];
  trades: TradeRow[];
  lifecycles: LifecycleRow[];
  shadow: ShadowRow[];
  taFeatures: TaFeatureRow[];
};
