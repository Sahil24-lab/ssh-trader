'use client';
/* 9.1 Overview – app/page.tsx
All pages share a common grid layout (2‑column on desktop, 1‑column on mobile).
Replace the placeholder fetchJSON URLs with your actual CSV/JSON endpoints.
*/
import { useEffect, useState } from 'react';
import { fetchJSON } from '@/lib/api';
import ChartCard from '@/components/ChartCard';
import LoadingSpinner from '@/components/LoadingSpinner';
import { RegimeBadge } from '@/components/RegimeBadge';

type OverviewData = {
  nav: number[];
  dates: string[];
  drawdown: number[];
  leverage: number[];
  exposure: number[];
  regime: ('RISK_ON' | 'NEUTRAL' | 'RISK_OFF')[];
};

export default function HomePage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const payload = await fetchJSON<OverviewData>('/api/overview');
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

  const regimeChart = {
    labels: data!.dates,
    datasets: [
      {
        label: 'Regime',
        data: data!.regime.map((r) => (r === 'RISK_ON' ? 2 : r === 'NEUTRAL' ? 1 : 0)),
        borderColor: '#0fa3b1',
        backgroundColor: 'rgba(15,163,177,0.2)',
        tension: 0.2,
      },
    ],
  };

  return (
    <section className="grid gap-6 md:grid-cols-2">
      {/* NAV */}
      <ChartCard title="NAV" chartData={navChart} />
      {/* Drawdown */}
      <ChartCard title="Drawdown %" chartData={drawdownChart} />
      {/* Leverage & Exposure */}
      <ChartCard
        title="Leverage & Gross Exposure"
        chartData={{
          labels: data!.dates,
          datasets: [
            {
              label: 'Leverage',
              data: data!.leverage,
              borderColor: '#0fa3b1',
              yAxisID: 'y',
            },
            {
              label: 'Gross Exposure',
              data: data!.exposure,
              borderColor: '#ffb400',
              yAxisID: 'y1',
            },
          ],
        }}
        chartOptions={{
          scales: {
            y: { type: 'linear', position: 'left', beginAtZero: true },
            y1: { type: 'linear', position: 'right', beginAtZero: true },
          },
        }}
      />
      {/* Regime timeline */}
      <ChartCard
        title="Regime Timeline"
        chartData={regimeChart}
        chartOptions={{
          plugins: { legend: { display: false } },
          scales: { x: { display: false } },
        }}
      />
      {/* Current risk snapshot */}
      <div className="bg-slate-800 rounded-lg shadow-sm p-4">
        <h2 className="text-lg font-headline mb-3 text-teal-300">Current Risk Snapshot</h2>
        <ul className="space-y-2">
          <li>
            <strong>Leverage:</strong>{' '}
            <span className="font-mono">{data!.leverage[data!.leverage.length - 1].toFixed(2)}x</span>{' '}
            <span className={data!.leverage.at(-1)! <= 1.5 ? 'text-teal-400' : 'text-amber-400'}>
              (limit 1.5x)
            </span>
          </li>
          <li>
            <strong>Venue Cap Utilization:</strong>{' '}
            <span className="font-mono">{(data!.exposure.at(-1)! * 100).toFixed(1)}%</span>{' '}
            <span className={data!.exposure.at(-1)! <= 0.3 ? 'text-teal-400' : 'text-amber-400'}>
              (limit 30%)
            </span>
          </li>
          <li>
            <strong>Drawdown Switch:</strong>{' '}
            <span className="font-mono">{data!.drawdown.at(-1)!.toFixed(1)}%</span>{' '}
            <span className={data!.drawdown.at(-1)! <= 20 ? 'text-teal-400' : 'text-amber-400'}>
              (kill‑switch @20%)
            </span>
          </li>
          <li>
            <strong>Regime:</strong>{' '}
            <RegimeBadge regime={data!.regime.at(-1)!} />
          </li>
        </ul>
      </div>
    </section>
  );
}
