"use client";
/* 6️⃣ Navbar (components/Navbar.tsx) */
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  BarChart2,
  Clock,
  Zap,
  TrendingUp,
  Shield,
  Database,
} from "lucide-react";
import clsx from "clsx";

type NavItem = {
  href: string;
  label: string;
  icon: React.ReactNode;
};

const items: NavItem[] = [
  { href: "/", label: "Overview", icon: <Home size={18} /> },
  { href: "/backtest", label: "Backtest", icon: <BarChart2 size={18} /> },
  { href: "/forward", label: "Forward", icon: <Clock size={18} /> },
  { href: "/live", label: "Live", icon: <Zap size={18} /> },
  { href: "/trades", label: "Trades", icon: <TrendingUp size={18} /> },
  { href: "/risk", label: "Risk", icon: <Shield size={18} /> },
  { href: "/data", label: "Data/Regime", icon: <Database size={18} /> },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="bg-slate-800 text-slate-100 shadow-md">
      <ul className="flex overflow-x-auto">
        {items.map((item) => {
          const isActive = pathname === item.href;
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                className={clsx(
                  "flex items-center gap-2 px-4 py-3 transition-colors",
                  isActive
                    ? "bg-teal-600 text-white"
                    : "hover:bg-slate-700 hover:text-teal-300",
                )}
              >
                {item.icon}
                <span className="font-medium">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
