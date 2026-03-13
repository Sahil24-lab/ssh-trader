/* 8.3 components/TableCard.tsx */
import { ReactNode } from 'react';

type TableColumn = {
  header: string;
  accessor: string;
  className?: string;
  render?: (value: any, row: any) => ReactNode;
};

type TableCardProps = {
  title: string;
  columns: TableColumn[];
  data: any[];
};

export default function TableCard({ title, columns, data }: TableCardProps) {
  return (
    <div className="bg-slate-800 rounded-lg shadow-sm p-4 overflow-x-auto">
      <h2 className="text-lg font-headline mb-3 text-teal-300">{title}</h2>
      <table className="w-full table-auto text-sm font-body">
        <thead>
          <tr className="text-slate-400">
            {columns.map((col) => (
              <th key={col.accessor} className={`px-2 py-1 ${col.className ?? ''}`}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={i}
              className="hover:bg-slate-700 transition-colors"
            >
              {columns.map((col) => {
                const value = row[col.accessor];
                return (
                  <td key={col.accessor} className={`px-2 py-1 ${col.className ?? ''}`}>
                    {col.render ? col.render(value, row) : value}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
