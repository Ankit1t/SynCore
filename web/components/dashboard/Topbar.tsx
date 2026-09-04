"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Wallet, Plus, Loader2, X } from "lucide-react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { useHistory } from "@/components/history/HistoryProvider";
import { useWallet } from "@/components/wallet/WalletProvider";

const money = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

export function Topbar() {
  const { selected } = useHistory();
  const { wallet, loading, topUp } = useWallet();
  const [showTopup, setShowTopup] = useState(false);
  const [amount, setAmount] = useState("");

  async function addMoney() {
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) return;
    const res = await topUp(value);
    if (res.ok) {
      setShowTopup(false);
      setAmount("");
    }
  }
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
        <div className="relative">
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
              onClick={() => setShowTopup((v) => !v)}
              disabled={loading}
              aria-label="Add money to wallet"
              className="ml-0.5 grid h-5 w-5 place-items-center rounded-md bg-accent/15 text-accent transition-colors hover:bg-accent/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50"
            >
              {loading ? (
                <Loader2 size={12} className="animate-spin" />
              ) : showTopup ? (
                <X size={13} />
              ) : (
                <Plus size={13} />
              )}
            </button>
          </motion.div>

          <AnimatePresence>
            {showTopup && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className="absolute right-0 top-12 z-30 w-64 rounded-xl border border-line bg-surface p-3 shadow-soft"
              >
                <p className="mb-2 text-xs font-medium">Add money to wallet</p>
                <div className="flex gap-2">
                  <input
                    type="number"
                    min={1}
                    inputMode="numeric"
                    autoFocus
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addMoney()}
                    placeholder="Enter amount (₹)"
                    className="min-w-0 flex-1 rounded-lg border border-line bg-elevated px-2.5 py-1.5 text-sm text-primary outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  />
                  <button
                    type="button"
                    onClick={addMoney}
                    disabled={loading || !amount}
                    className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:brightness-110 disabled:opacity-50"
                  >
                    {loading ? <Loader2 size={14} className="animate-spin" /> : "Add"}
                  </button>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {[500, 1000, 2000, 5000].map((v) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setAmount(String(v))}
                      className="rounded-md border border-line px-2 py-0.5 text-[11px] text-muted transition-colors hover:border-accent/50 hover:text-primary"
                    >
                      ₹{v}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-[10px] text-muted">
                  Paid via Razorpay test mode · then orders auto-settle from wallet.
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
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
