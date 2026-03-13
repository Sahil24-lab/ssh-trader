'use client';
/* 9.7 Data / Regime – app/data/page.tsx */
import { useEffect, useState } from 'react';
import { fetchJSON } from '@/lib/api';
import TableCard from '@/components/TableCard';
import LoadingSpinner from '@/components/LoadingSpinner';
import { RegimeBadge } from '@/components/RegimeBadge';

type RegimeFeature = {
  timestamp: string;
  regime: 'RISK_ON' | 'NEUTRAL' | 'RISK_OFF';
  feature_set: Record<string, number>;
};

export default function DataPage() {
  const [features, setFeatures] = useState<RegimeFeature[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const payload = await fetchJSON<RegimeFeature[]>('/api/feature-regime');
      setFeatures(payload);
      setLoading(false);
    })();
  }, []);

  if (loading) return <LoadingSpinner />;

  const columns = [
    { header: 'Time', accessor: 'timestamp' },
    { header: 'Regime', accessor: 'regime', render: (val: any) => <RegimeBadge regime={val} /> },
    // Dynamically list a few key features (example: vol, momentum)
    { header: 'Volatility', accessor: 'feature_set.volatility', className: 'font-mono' },
    { header: 'Momentum', accessor: 'feature_set.momentum', className: 'font-mono' },
    { header: 'Funding Rate', accessor: 'feature_set.funding_rate', className: 'font-mono' },
  ];

  // Transform data for TableCard (flatten feature_set)
  const rows = features.map((f) => ({
    timestamp: f.timestamp,
    regime: f.regime,
    'feature_set.volatility': f.feature_set.volatility?.toFixed(4) ?? '',
    'feature_set.momentum': f.feature_set.momentum?.toFixed(4) ?? '',
    'feature_set.funding_rate': f.feature_set.funding_rate?.toFixed(4) ?? '',
  }));

  return (
    <section>
      <TableCard title="Regime & Feature Log" columns={columns} data={rows} />
    </section>
  );
}
