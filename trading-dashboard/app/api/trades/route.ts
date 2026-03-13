/* Create similar mock files for /api/trades */
import { NextResponse } from 'next/server';

export async function GET() {
  const mock = [
    {
      id: 'T-001',
      open: '2024-01-02T03:45:00Z',
      close: '2024-01-04T10:12:00Z',
      side: 'LONG',
      size: 0.75,
      entry_price: 28500.12,
      exit_price: 29100.55,
      funding: -0.0008,
      fees: -0.0012,
      slippage: -0.0003,
      pnl: 450.23,
      r_multiple: 1.8,
      mae: -120.5,
      mfe: 300.0,
      regime_at_open: 'RISK_ON',
      regime_at_close: 'NEUTRAL',
    },
    {
      id: 'T-002',
      open: '2024-01-05T06:20:00Z',
      close: '2024-01-06T14:05:00Z',
      side: 'SHORT',
      size: 0.4,
      entry_price: 29400.0,
      exit_price: 28950.0,
      funding: -0.0004,
      fees: -0.0008,
      slippage: -0.0002,
      pnl: 180.5,
      r_multiple: 1.2,
      mae: -90.0,
      mfe: 210.0,
      regime_at_open: 'NEUTRAL',
      regime_at_close: 'RISK_OFF',
    },
  ];

  return NextResponse.json(mock);
}
