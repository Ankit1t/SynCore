"use client";

import { motion } from "framer-motion";
import { Wallet, Plus, Loader2 } from "lucide-react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { useHistory } from "@/components/history/HistoryProvider";
import { useWallet } from "@/components/wallet/WalletProvider";

const money = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

export function Topbar() {
  const { selected } = useHistory();
  const { wallet, loading, topUp } = useWallet();
  const budget = selected?.result.understanding.budget_inr ?? null;
  const total = selected?.result.basket.total ?? null;
  const within = selected?.result.budget_check.within_budget ?? true;

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-line bg-bg/70 px-5 backdrop-blur-xl">
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-sm font-semibold sm:text-base">AI Shopping Assistant</h1>
        <p className="hidden text-xs text-muted sm:block">
          One instruction — your agent builds the basket and guards the budget.
        </p>
      </div>

      {budget != null && total != null && (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          className="hidden items-center gap-2 rounded-xl border border-line bg-surface px-3 py-1.5 md:flex"
        >
          <Wallet size={15} className={within ? "text-good" : "text-bad"} />
          <span className="text-xs text-muted">Budget</span>
          <span className="text-sm font-semibold tabular-nums">
            {money(total)}
            <span className="text-muted"> / {money(budget)}</span>
          </span>
        </motion.div>
      )}

      {wallet && (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex items-center gap-2 rounded-xl border border-line bg-surface px-2.5 py-1.5"
          title="Prepaid wallet balance"
        >
          <Wallet size={15} className="text-accent" />
          <span className="text-sm font-semibold tabular-nums">{money(wallet.balance_inr)}</span>
          <button
            type="button"
            onClick={() => topUp(5000)}
            disabled={loading}
            aria-label="Top up wallet by 500 rupees"
            className="ml-0.5 grid h-5 w-5 place-items-center rounded-md bg-accent/15 text-accent transition-colors hover:bg-accent/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <Plus size={13} />}
          </button>
        </motion.div>
      )}

      <ThemeToggle />

      <div
        className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-accent to-good text-xs font-bold text-white"
        aria-label="User"
        title="You"
      >
        AK
      </div>
    </header>
  );
}
