'use client';
/* 9.5 Trades – app/trades/page.tsx */
import { useEffect, useState } from 'react';
import { fetchJSON } from '@/lib/api';
import TableCard from '@/components/TableCard';
import LoadingSpinner from '@/components/LoadingSpinner';
import { RegimeBadge } from '@/components/RegimeBadge';

type Trade = {
  id: string;
  open: string;
  close: string;
  side: 'LONG' | 'SHORT';
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

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const payload = await fetchJSON<Trade[]>('/api/trades');
      setTrades(payload);
      setLoading(false);
    })();
  }, []);

  if (loading) return <LoadingSpinner />;

  const columns = [
    { header: 'ID', accessor: 'id', className: 'font-mono' },
    { header: 'Open', accessor: 'open' },
    { header: 'Close', accessor: 'close' },
    { header: 'Side', accessor: 'side' },
    { header: 'Size', accessor: 'size', className: 'font-mono' },
    { header: 'PnL', accessor: 'pnl', className: 'font-mono' },
    { header: 'R‑Multiple', accessor: 'r_multiple', className: 'font-mono' },
    { header: 'MAE', accessor: 'mae', className: 'font-mono' },
    { header: 'MFE', accessor: 'mfe', className: 'font-mono' },
    { header: 'Regime (Open)', accessor: 'regime_at_open' },
    { header: 'Regime (Close)', accessor: 'regime_at_close' },
  ];

  return (
    <section>
      <TableCard title="Closed Trades – Full Lifecycle" columns={columns} data={trades} />
    </section>
  );
}
