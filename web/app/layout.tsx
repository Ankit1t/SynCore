import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { HistoryProvider } from "@/components/history/HistoryProvider";
import { WalletProvider } from "@/components/wallet/WalletProvider";
import { DashboardShell } from "@/components/dashboard/DashboardShell";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "SynCore — AI Shopping Assistant",
  description: "Give one instruction — your agent builds the basket and guards your budget.",
};

// Set the theme class before paint to avoid a light/dark flash.
const themeScript = `(function(){try{var t=localStorage.getItem('syncore-theme');var d=t?t==='dark':!window.matchMedia('(prefers-color-scheme: light)').matches;document.documentElement.classList.toggle('dark',d);}catch(e){document.documentElement.classList.add('dark');}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="font-sans antialiased">
        <ThemeProvider>
          <HistoryProvider>
            <WalletProvider>
              <DashboardShell>{children}</DashboardShell>
            </WalletProvider>
          </HistoryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
