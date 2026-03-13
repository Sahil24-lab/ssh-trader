/* 3️⃣ Define the TypeScript types (optional but recommended) */
// Types that describe a single back‑test trade row
export type BacktestTrade = {
  id: string;
  open: string;          // ISO‑8601 timestamp
  close: string;         // ISO‑8601 timestamp
  side: 'LONG' | 'SHORT' | 'CARRY';
  size: number;
  entry_price: number;
  exit_price: number;
  funding: number;
  fees: number;
  slippage: number;
  pnl: number;
  r_multiple: number;
  mae: number;
  mfe: number;
  regime_at_open: 'RISK_ON' | 'NEUTRAL' | 'RISK_OFF';
  regime_at_close: 'RISK_ON' | 'NEUTRAL' | 'RISK_OFF';
};

// The full payload returned by the API
export type BacktestPayload = {
  nav: number[];
  dates: string[];
  drawdown: number[];
  regime: ('RISK_ON' | 'NEUTRAL' | 'RISK_OFF')[];
  trades: BacktestTrade[];
};
