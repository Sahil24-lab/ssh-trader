/* Create similar mock files for /api/forward */
import { NextResponse } from 'next/server';

export async function GET() {
  const mock = {
    intendedOrders: [
      {
        id: 'FWD-001',
        timestamp: '2024-01-10T09:00:00Z',
        side: 'LONG',
        size: 0.5,
        price: 31250.0,
        reason: 'RISK_ON overlay signal',
      },
      {
        id: 'FWD-002',
        timestamp: '2024-01-10T12:00:00Z',
        side: 'CARRY',
        size: 1.0,
        price: 0,
        reason: 'Carry rebalance',
      },
    ],
    hypotheticalFills: [
      {
        order_id: 'FWD-001',
        fill_price: 31270.5,
        slippage_est: 0.08,
        venue: 'HYPERLIQUID',
      },
      {
        order_id: 'FWD-002',
        fill_price: 0,
        slippage_est: 0.0,
        venue: 'HYPERLIQUID',
      },
    ],
  };

  return NextResponse.json(mock);
}
