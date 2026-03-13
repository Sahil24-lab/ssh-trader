/* 5️⃣ Layout & Navigation (app/layout.tsx) */
import './globals.css';
import Navbar from '@/components/Navbar';
import { Inter } from 'next/font/google';

export const metadata = {
  title: 'Regime‑Adaptive Crypto Dashboard',
  description: 'Live, back‑test and forward‑test view of a GNC trading system',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="flex flex-col min-h-screen">
        <Navbar />
        <main className="flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </body>
    </html>
  );
}
