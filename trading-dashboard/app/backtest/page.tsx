'use client';
/* 9.2 Backtest – app/backtest/page.tsx */
import { useEffect, useState } from 'react';
import { fetchJSON } from '@/lib/api';
import ChartCard from '@/components/ChartCard';
import TableCard from '@/components/TableCard';
import LoadingSpinner from '@/components/LoadingSpinner';

type BacktestTrade = {
  id: string;
  open: string;
  close: string;
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
  regime_at_open: string;
  regime_at_close: string;
};

type BacktestData = {
  nav: number[];
  dates: string[];
  drawdown: number[];
  regime: ('RISK_ON' | 'NEUTRAL' | 'RISK_OFF')[];
  trades: BacktestTrade[];
};

export default function BacktestPage() {
  const [data, setData] = useState<BacktestData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const payload = await fetchJSON<BacktestData>('/api/backtest');
      setData(payload);
      setLoading(false);
    })();
  }, []);

  if (loading) return <LoadingSpinner />;

  const navChart = {
    labels: data!.dates,
    datasets: [
      {
        label: 'NAV',
        data: data!.nav,
        borderColor: '#0fa3b1',
        backgroundColor: 'rgba(15,163,177,0.1)',
        tension: 0.2,
        fill: true,
      },
    ],
  };

  const drawdownChart = {
    labels: data!.dates,
    datasets: [
      {
        label: 'Drawdown %',
        data: data!.drawdown,
        borderColor: '#ffb400',
        tension: 0.2,
      },
    ],
  };

  // Separate directional vs carry trades
  const directional = data!.trades.filter((t) => t.side !== 'CARRY');
  const carry = data!.trades.filter((t) => t.side === 'CARRY');

  const tradeColumns = [
    { header: 'ID', accessor: 'id', className: 'font-mono' },
    { header: 'Open', accessor: 'open' },
    { header: 'Close', accessor: 'close' },
    { header: 'Side', accessor: 'side' },
    { header: 'Size', accessor: 'size', className: 'font-mono' },
    { header: 'P&L', accessor: 'pnl', className: 'font-mono' },
    { header: 'R‑Multiple', accessor: 'r_multiple', className: 'font-mono' },
    { header: 'Regime (Open)', accessor: 'regime_at_open' },
    { header: 'Regime (Close)', accessor: 'regime_at_close' },
  ];

  return (
    <section className="grid gap-6 md:grid-cols-2">
      {/* NAV & Drawdown */}
      <ChartCard title="Backtest NAV" chartData={navChart} />
      <ChartCard title="Backtest Drawdown %" chartData={drawdownChart} />
      {/* Directional trades */}
      <TableCard title="Directional Trades" columns={tradeColumns} data={directional} />
      {/* Carry rebalances */}
      <TableCard title="Carry Rebalances" columns={tradeColumns} data={carry} />
      {/* Regime timeline (tiny) */}
      <ChartCard
        title="Regime Timeline"
        chartData={{
          labels: data!.dates,
          datasets: [
            {
              label: 'Regime',
              data: data!.regime.map((r) => (r === 'RISK_ON' ? 2 : r === 'NEUTRAL' ? 1 : 0)),
              backgroundColor: data!.regime.map((r) =>
                r === 'RISK_ON' ? '#0fa3b1' : r === 'NEUTRAL' ? '#ffb400' : '#6b7280'
              ),
              borderWidth: 0,
            },
          ],
        }}
        chartOptions={{
          plugins: { legend: { display: false } },
          scales: { x: { display: false } },
        }}
      />
    </section>
  );
}
