/* 10️⃣ API routes (placeholder – you will replace with real data sources)
// pages/api/overview.ts
*/
import { NextResponse } from 'next/server';

export async function GET() {
  const mock = {
    nav: [100, 102, 101, 105, 108],
    dates: ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'],
    drawdown: [0, 0.5, 0.3, 0, 0],
    leverage: [1.2, 1.3, 1.1, 1.4, 1.2],
    exposure: [0.25, 0.28, 0.22, 0.30, 0.27],
    regime: ['RISK_ON', 'RISK_ON', 'NEUTRAL', 'RISK_OFF', 'NEUTRAL'],
  };

  return NextResponse.json(mock);
}
