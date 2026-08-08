import "./globals.css";
import type { Metadata } from "next";
import { ReactNode } from "react";
import { AppHeader } from "@/components/AppHeader";

export const metadata: Metadata = {
  title: "Trading Research Dashboard",
  description: "Crypto trading research and shadow-mode dashboard."
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-background text-uiTextPrimary antialiased" suppressHydrationWarning>
        <AppHeader />
        {children}
      </body>
    </html>
  );
}
