/* 4️⃣ CSV‑to‑JSON API route (app/api/backtest/route.ts)
What the route expects from data/backtest.csv (column headers):
- type: nav or trade
- date: 2024-01-01
- nav: 102.34
- drawdown: 0.45
- regime: RISK_ON
- id: T-00123
- open: 2024-01-02T03:45:00Z
- close: 2024-01-04T10:12:00Z
- side: LONG / SHORT / CARRY
- size: 0.75
- entry_price: 28500.12
- exit_price: 29100.55
- funding: -0.0008
- fees: -0.0012
- slippage: -0.0003
- pnl: 450.23
- r_multiple: 1.8
- mae: -120.5
- mfe: 300.0
- regime_at_open: RISK_ON
- regime_at_close: NEUTRAL
*/
import { NextResponse } from 'next/server';
import { createReadStream } from 'fs';
import { resolve } from 'path';
import { parse } from 'csv-parse/sync';
import type { BacktestPayload, BacktestTrade } from '@/lib/types';

// ---------------------------------------------------------------------------
// Helper: convert a CSV row (all strings) into the proper typed object
// ---------------------------------------------------------------------------
function rowToTrade(row: Record<string, string>): BacktestTrade {
  return {
    id: row.id,
    open: row.open,
    close: row.close,
    side: row.side as 'LONG' | 'SHORT' | 'CARRY',
    size: Number(row.size),
    entry_price: Number(row.entry_price),
    exit_price: Number(row.exit_price),
    funding: Number(row.funding),
    fees: Number(row.fees),
    slippage: Number(row.slippage),
    pnl: Number(row.pnl),
    r_multiple: Number(row.r_multiple),
    mae: Number(row.mae),
    mfe: Number(row.mfe),
    regime_at_open: row.regime_at_open as 'RISK_ON' | 'NEUTRAL' | 'RISK_OFF',
    regime_at_close: row.regime_at_close as 'RISK_ON' | 'NEUTRAL' | 'RISK_OFF',
  };
}

// ---------------------------------------------------------------------------
// Main handler – reads CSV, builds the payload, returns JSON
// ---------------------------------------------------------------------------
export async function GET() {
  try {
    // Resolve the CSV location relative to the project root
    const csvPath = resolve(process.cwd(), 'data', 'backtest.csv');

    // Synchronously read the whole file (fast enough for a few MB)
    const csvContent = await new Promise<string>((resolve, reject) => {
      let data = '';
      createReadStream(csvPath)
        .setEncoding('utf8')
        .on('data', (chunk) => (data += chunk))
        .on('end', () => resolve(data))
        .on('error', reject);
    });

    // Parse CSV – first line must be a header row
    const records: Record<string, string>[] = parse(csvContent, {
      columns: true,            // use header row as object keys
      skip_empty_lines: true,
      trim: true,
    });

    // Split the file into two logical sections:
    //   1️⃣ NAV / time‑series data (first N rows, identified by a column "type" = "nav")
    //   2️⃣ Trade rows (type = "trade")
    // Adjust the column names to match your export format.
    const navRows = records.filter((r) => r.type === 'nav');
    const tradeRows = records.filter((r) => r.type === 'trade');

    // Build the time‑series arrays
    const nav = navRows.map((r) => Number(r.nav));
    const dates = navRows.map((r) => r.date);
    const drawdown = navRows.map((r) => Number(r.drawdown));
    const regime = navRows.map(
      (r) => r.regime as 'RISK_ON' | 'NEUTRAL' | 'RISK_OFF'
    );

    // Build the trade objects
    const trades = tradeRows.map(rowToTrade);

    const payload: BacktestPayload = {
      nav,
      dates,
      drawdown,
      regime,
      trades,
    };

    return NextResponse.json(payload);
  } catch (err) {
    console.error('❌ Backtest CSV load failed:', err);
    return new NextResponse('Failed to load backtest data', { status: 500 });
  }
}
