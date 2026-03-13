/* Create similar mock files for /api/feature-regime */
import { NextResponse } from 'next/server';

export async function GET() {
  const mock = [
    {
      timestamp: '2024-01-03T00:00:00Z',
      regime: 'RISK_ON',
      feature_set: {
        volatility: 0.0123,
        momentum: 0.0456,
        funding_rate: 0.0002,
      },
    },
    {
      timestamp: '2024-01-04T00:00:00Z',
      regime: 'NEUTRAL',
      feature_set: {
        volatility: 0.0187,
        momentum: -0.0124,
        funding_rate: -0.0001,
      },
    },
    {
      timestamp: '2024-01-05T00:00:00Z',
      regime: 'RISK_OFF',
      feature_set: {
        volatility: 0.0275,
        momentum: -0.0333,
        funding_rate: -0.0004,
      },
    },
  ];

  return NextResponse.json(mock);
}
