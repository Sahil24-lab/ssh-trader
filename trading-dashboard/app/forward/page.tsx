'use client';
/* 9.3 Forward Test (shadow) – app/forward/page.tsx */
import { useEffect, useState } from 'react';
import { fetchJSON } from '@/lib/api';
import TableCard from '@/components/TableCard';
import LoadingSpinner from '@/components/LoadingSpinner';
import { RegimeBadge } from '@/components/RegimeBadge';

type ForwardData = {
  intendedOrders: {
    id: string;
    timestamp: string;
    side: 'LONG' | 'SHORT' | 'CARRY';
    size: number;
    price: number;
    reason: string;
  }[];
  hypotheticalFills: {
    order_id: string;
    fill_price: number;
    slippage_est: number;
    venue: string;
  }[];
};

export default function ForwardPage() {
  const [data, setData] = useState<ForwardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const payload = await fetchJSON<ForwardData>('/api/forward');
      setData(payload);
      setLoading(false);
    })();
  }, []);

  if (loading) return <LoadingSpinner />;

  const orderColumns = [
    { header: 'ID', accessor: 'id', className: 'font-mono' },
    { header: 'Time', accessor: 'timestamp' },
    { header: 'Side', accessor: 'side' },
    { header: 'Size', accessor: 'size', className: 'font-mono' },
    { header: 'Price', accessor: 'price', className: 'font-mono' },
    { header: 'Reason', accessor: 'reason' },
  ];

  const fillColumns = [
    { header: 'Order ID', accessor: 'order_id', className: 'font-mono' },
    { header: 'Fill Price', accessor: 'fill_price', className: 'font-mono' },
    { header: 'Slippage %', accessor: 'slippage_est', className: 'font-mono' },
    { header: 'Venue', accessor: 'venue' },
  ];

  return (
    <section className="grid gap-6 md:grid-cols-2">
      <TableCard title="Intended Orders (Shadow)" columns={orderColumns} data={data!.intendedOrders} />
      <TableCard title="Hypothetical Fills" columns={fillColumns} data={data!.hypotheticalFills} />
    </section>
  );
}
