"use client";

import { motion } from "framer-motion";
import { Wallet } from "lucide-react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { useHistory } from "@/components/history/HistoryProvider";

const money = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

export function Topbar() {
  const { selected } = useHistory();
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
