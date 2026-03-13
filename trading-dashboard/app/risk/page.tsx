'use client';
/* 9.6 Risk – app/risk/page.tsx */
import { useEffect, useState } from 'react';
import { fetchJSON } from '@/lib/api';
import ChartCard from '@/components/ChartCard';
import LoadingSpinner from '@/components/LoadingSpinner';

type RiskMetrics = {
  dates: string[];
  leverage: number[];
  venueCap: number[];
  drawdown: number[];
  regime: ('RISK_ON' | 'NEUTRAL' | 'RISK_OFF')[];
};

export default function RiskPage() {
  const [data, setData] = useState<RiskMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const payload = await fetchJSON<RiskMetrics>('/api/risk');
      setData(payload);
      setLoading(false);
    })();
  }, []);

  if (loading) return <LoadingSpinner />;

  const leverageChart = {
    labels: data!.dates,
    datasets: [
      {
        label: 'Leverage',
        data: data!.leverage,
        borderColor: '#0fa3b1',
        tension: 0.2,
      },
    ],
  };

  const venueChart = {
    labels: data!.dates,
    datasets: [
      {
        label: 'Venue Cap %',
        data: data!.venueCap.map((v) => v * 100),
        borderColor: '#ffb400',
        tension: 0.2,
      },
    ],
  };

  const drawdownChart = {
    labels: data!.dates,
    datasets: [
      {
        label: 'Drawdown %',
        data: data!.drawdown,
        borderColor: '#ff5f57',
        tension: 0.2,
      },
    ],
  };

  const regimeChart = {
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
  };

  return (
    <section className="grid gap-6 md:grid-cols-2">
      <ChartCard title="Leverage Over Time" chartData={leverageChart} />
      <ChartCard title="Venue Cap Utilization (%)" chartData={venueChart} />
      <ChartCard title="Drawdown (%)" chartData={drawdownChart} />
      <ChartCard
        title="Regime Timeline"
        chartData={regimeChart}
        chartOptions={{
          plugins: { legend: { display: false } },
          scales: { x: { display: false } },
        }}
      />
    </section>
  );
}
