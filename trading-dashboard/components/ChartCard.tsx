'use client';
/* 8.2 components/ChartCard.tsx */
import { ReactNode } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend } from 'chart.js';
import { Line } from 'react-chartjs-2';
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

type Props = {
  title: string;
  chartData: any;
  chartOptions?: any;
  children?: ReactNode; // optional controls
};

export default function ChartCard({ title, chartData, chartOptions, children }: Props) {
  return (
    <div className="bg-slate-800 rounded-lg shadow-sm p-4">
      <div className="flex justify-between items-center mb-2">
        <h2 className="text-lg font-headline text-teal-300">{title}</h2>
        {children}
      </div>
      <Line data={chartData} options={chartOptions} />
    </div>
  );
}
