import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Syncore — AI Shopping Agent",
  description: "Tell your agent what to buy — it will handle the rest.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="flex items-center gap-4 border-b border-line px-7 py-4">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-good font-extrabold text-bg"
            aria-hidden="true"
          >
            S
          </div>
          <div className="flex-1">
            <h1 className="text-lg font-semibold tracking-wide">Syncore</h1>
            <p className="text-xs text-muted">Your autonomous shopping agent</p>
          </div>
          <nav className="flex gap-4 text-sm text-muted" aria-label="Primary">
            <Link href="/" className="rounded hover:text-white focus-visible:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
              Shop
            </Link>
            <Link href="/orders" className="rounded hover:text-white focus-visible:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
              Orders
            </Link>
            <Link href="/preferences" className="rounded hover:text-white focus-visible:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
              Preferences
            </Link>
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-7 py-6">{children}</main>
      </body>
    </html>
  );
}
