/* Create similar mock files for /api/live */
import { NextResponse } from 'next/server';

export async function GET() {
  const mock = {
    risk: {
      leverage: 1.12,
      venueCapUtil: 0.27,
      drawdown: 4.3,
      regime: 'NEUTRAL',
    },
    balances: [
      { asset: 'USDC', amount: 25000, usdValue: 25000 },
      { asset: 'BTC', amount: 0.85, usdValue: 28900 },
    ],
    openPositions: [
      {
        id: 'POS-01',
        side: 'LONG',
        size: 0.4,
        entryPrice: 30250,
        currentPrice: 30510,
        pnl: 104,
        venue: 'HYPERLIQUID',
      },
      {
        id: 'POS-02',
        side: 'SHORT',
        size: 0.2,
        entryPrice: 30900,
        currentPrice: 30510,
        pnl: 78,
        venue: 'HYPERLIQUID',
      },
    ],
    executionQueue: [
      { id: 'EXQ-01', status: 'PENDING', createdAt: '2024-01-10T10:05:00Z' },
      { id: 'EXQ-02', status: 'QUEUED', createdAt: '2024-01-10T10:06:00Z' },
    ],
  };

  return NextResponse.json(mock);
}
