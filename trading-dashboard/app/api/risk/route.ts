/* Create similar mock files for /api/risk */
import { NextResponse } from 'next/server';

export async function GET() {
  const mock = {
    dates: ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'],
    leverage: [1.05, 1.12, 1.08, 1.15, 1.1],
    venueCap: [0.22, 0.25, 0.24, 0.28, 0.26],
    drawdown: [0, 0.6, 0.4, 0.2, 0.5],
    regime: ['RISK_ON', 'RISK_ON', 'NEUTRAL', 'RISK_OFF', 'NEUTRAL'],
  };

  return NextResponse.json(mock);
}
