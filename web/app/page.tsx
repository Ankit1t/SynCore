"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, HelpCircle } from "lucide-react";
import { Composer } from "@/components/dashboard/Composer";
import { ActivityTimeline } from "@/components/dashboard/ActivityTimeline";
import { BasketPanel } from "@/components/dashboard/BasketPanel";
import { ReviewBadge } from "@/components/dashboard/ReviewBadge";
import { Card } from "@/components/ui/Card";
import { useHistory } from "@/components/history/HistoryProvider";
import { askAgent } from "@/lib/api";
import { friendlyError } from "@/lib/labels";

export default function ShopPage() {
  const { selected, add } = useHistory();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // While a request is in flight we show loading states, otherwise the
  // currently selected history entry.
  const result = running ? null : selected?.result ?? null;

  async function run(query: string) {
    setError(null);
    setRunning(true);
    try {
      const res = await askAgent(query);
      add(query, res);
    } catch {
      setError(friendlyError("agent request failed"));
    } finally {
      setRunning(false);
    }
  }

  const msg = result?.message_to_user;
  const action = result?.next_action;
  const banner =
    action === "PROCEED_TO_CHECKOUT"
      ? { cls: "border-good/40 bg-good/10 text-good", Icon: CheckCircle2 }
      : action === "ASK_USER"
        ? { cls: "border-warn/40 bg-warn/10 text-warn", Icon: HelpCircle }
        : { cls: "border-line bg-surface text-primary", Icon: HelpCircle };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 26 }}
        className="mb-6"
      >
        <h2 className="text-2xl font-semibold tracking-tight">What can I get for you?</h2>
        <p className="mt-1 text-sm text-muted">
          Give one instruction — anything, not just groceries. Your agent understands it, builds the
          best basket, and keeps it within budget.
        </p>
      </motion.div>

      <Composer running={running} onSubmit={run} />

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            role="alert"
            className="mt-4 flex items-center gap-2 rounded-xl border border-bad/40 bg-bad/10 p-3 text-sm text-bad"
          >
            <AlertTriangle size={16} />
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {msg && !running && (
          <motion.div
            key={msg}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            aria-live="polite"
            className={`mt-4 flex items-start gap-2 rounded-xl border p-3 text-sm ${banner.cls}`}
          >
            <banner.Icon size={16} className="mt-0.5 shrink-0" />
            <span>{msg}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-5">
        <Card className="p-5 lg:col-span-3">
          <ActivityTimeline result={result} running={running} />
          {result?.review && !running && <ReviewBadge review={result.review} />}
        </Card>
        <Card className="p-5 lg:col-span-2">
          <BasketPanel result={result} running={running} />
        </Card>
      </div>
    </div>
  );
}
