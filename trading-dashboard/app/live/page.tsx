'use client';
/* 9.4 Live – app/live/page.tsx */
import { useEffect, useState } from 'react';
import { fetchJSON } from '@/lib/api';
import ChartCard from '@/components/ChartCard';
import TableCard from '@/components/TableCard';
import LoadingSpinner from '@/components/LoadingSpinner';
import { RegimeBadge } from '@/components/RegimeBadge';

type LiveData = {
  risk: {
    leverage: number;
    venueCapUtil: number;
    drawdown: number;
    regime: 'RISK_ON' | 'NEUTRAL' | 'RISK_OFF';
  };
  balances: {
    asset: string;
    amount: number;
    usdValue: number;
  }[];
  openPositions: {
    id: string;
    side: string;
    size: number;
    entryPrice: number;
    currentPrice: number;
    pnl: number;
    venue: string;
  }[];
  executionQueue: {
    id: string;
    status: string;
    createdAt: string;
  }[];
};

export default function LivePage() {
  const [data, setData] = useState<LiveData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const payload = await fetchJSON<LiveData>('/api/live');
      setData(payload);
      setLoading(false);
    })();
  }, []);

  if (loading) return <LoadingSpinner />;

  const riskChart = {
    labels: ['Leverage', 'Venue Cap', 'Drawdown'],
    datasets: [
      {
        label: 'Current',
        data: [data!.risk.leverage, data!.risk.venueCapUtil * 100, data!.risk.drawdown],
        borderColor: '#0fa3b1',
        backgroundColor: 'rgba(15,163,177,0.2)',
      },
    ],
  };

  return (
    <section className="grid gap-6 md:grid-cols-2">
      {/* Risk snapshot */}
      <div className="bg-slate-800 rounded-lg shadow-sm p-4">
        <h2 className="text-lg font-headline mb-3 text-teal-300">Live Risk Snapshot</h2>
        <ul className="space-y-2">
          <li>
            <strong>Leverage:</strong>{' '}
            <span className="font-mono">{data!.risk.leverage.toFixed(2)}x</span>{' '}
            <span className={data!.risk.leverage <= 1.5 ? 'text-teal-400' : 'text-amber-400'}>
              (limit 1.5x)
            </span>
          </li>
          <li>
            <strong>Venue Cap Utilization:</strong>{' '}
            <span className="font-mono">{(data!.risk.venueCapUtil * 100).toFixed(1)}%</span>{' '}
            <span className={data!.risk.venueCapUtil <= 0.3 ? 'text-teal-400' : 'text-amber-400'}>
              (limit 30%)
            </span>
          </li>
          <li>
            <strong>Drawdown:</strong>{' '}
            <span className="font-mono">{data!.risk.drawdown.toFixed(1)}%</span>{' '}
            <span className={data!.risk.drawdown <= 20 ? 'text-teal-400' : 'text-amber-400'}>
              (kill‑switch @20%)
            </span>
          </li>
          <li>
            <strong>Regime:</strong>{' '}
            <RegimeBadge regime={data!.risk.regime} />
          </li>
        </ul>
      </div>

      {/* Risk chart */}
      <ChartCard title="Live Risk Indicators" chartData={riskChart} chartOptions={{ indexAxis: 'y' }} />

      {/* Balances */}
      <TableCard
        title="Balances (USD)"
        columns={[
          { header: 'Asset', accessor: 'asset' },
          { header: 'Amount', accessor: 'amount', className: 'font-mono' },
          { header: 'USD Value', accessor: 'usdValue', className: 'font-mono' },
        ]}
        data={data!.balances}
      />

      {/* Open positions */}
      <TableCard
        title="Open Positions"
        columns={[
          { header: 'ID', accessor: 'id', className: 'font-mono' },
          { header: 'Side', accessor: 'side' },
          { header: 'Size', accessor: 'size', className: 'font-mono' },
          { header: 'Entry', accessor: 'entryPrice', className: 'font-mono' },
          { header: 'Current', accessor: 'currentPrice', className: 'font-mono' },
          { header: 'PnL', accessor: 'pnl', className: 'font-mono' },
          { header: 'Venue', accessor: 'venue' },
        ]}
        data={data!.openPositions}
      />

      {/* Execution queue */}
      <TableCard
        title="Execution Queue"
        columns={[
          { header: 'ID', accessor: 'id', className: 'font-mono' },
          { header: 'Status', accessor: 'status' },
          { header: 'Created', accessor: 'createdAt' },
        ]}
        data={data!.executionQueue}
      />
    </section>
  );
}
