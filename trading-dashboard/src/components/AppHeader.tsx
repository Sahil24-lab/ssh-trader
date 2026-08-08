"use client";

import Link from "next/link";
import type { MouseEvent } from "react";

const views = [
  { label: "Overview", href: "/dashboard#overview" },
  { label: "Run", href: "/dashboard#run" },
  { label: "Charts", href: "/dashboard#charts" },
  { label: "Events", href: "/dashboard#events" },
  { label: "Trades", href: "/dashboard#trades" }
];

export function AppHeader() {
  function scrollToView(event: MouseEvent<HTMLAnchorElement>, href: string) {
    const hash = href.split("#")[1];
    if (!hash || window.location.pathname !== "/dashboard") return;
    const target = document.getElementById(hash);
    if (!target) return;
    event.preventDefault();
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    window.history.replaceState(null, "", href);
  }

  return (
    <header className="sticky top-0 z-[900] border-b border-uiBorderMedium bg-background/98 backdrop-blur-lg backdrop-saturate-150">
      <div className="mx-auto flex max-w-[1760px] flex-col gap-3 px-5 py-3 md:flex-row md:items-center md:justify-between">
        <Link href="/dashboard" className="group flex min-h-11 min-w-0 items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 font-mono text-[13px] font-bold text-primary transition group-hover:border-primary/60">
            ST
          </span>
          <span className="min-w-0">
            <span className="block text-[14px] font-bold leading-none tracking-tight text-uiTextPrimary">
              SSH Trader
            </span>
            <span className="mt-1 block truncate text-[11px] font-semibold uppercase tracking-[0.14em] text-uiTextSecondary">
              Research Dashboard
            </span>
          </span>
        </Link>

        <nav aria-label="Dashboard views" className="thin-scrollbar -mx-1 flex gap-1 overflow-x-auto px-1">
          {views.map((view) => (
            <Link
              key={view.href}
              href={view.href}
              onClick={(event) => scrollToView(event, view.href)}
              className="inline-flex min-h-11 items-center whitespace-nowrap rounded-lg px-3 py-2 text-[12px] font-bold text-uiTextSecondary transition hover:bg-uiHover hover:text-uiTextPrimary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
            >
              {view.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
