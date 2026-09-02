"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ShoppingCart, Tag, Info } from "lucide-react";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Skeleton } from "@/components/ui/Skeleton";
import type { DecideResponse } from "@/lib/api";

const money = (n: number) => `₹${(Math.round(n * 100) / 100).toLocaleString("en-IN")}`;

function qtyLabel(quantity: number, unit: string) {
  const q = Number.isInteger(quantity) ? quantity : Math.round(quantity * 100) / 100;
  return `${q} ${unit}`;
}

export function BasketPanel({
  result,
  running,
}: {
  result: DecideResponse | null;
  running: boolean;
}) {
  return (
    <section aria-labelledby="basket-heading" className="flex h-full flex-col">
      <div className="mb-4 flex items-center gap-2">
        <ShoppingCart size={16} className="text-accent" />
        <h3 id="basket-heading" className="text-sm font-semibold">
          Recommended Basket
        </h3>
      </div>

      {running ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center justify-between gap-3">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-4 w-10" />
            </div>
          ))}
          <Skeleton className="mt-4 h-2 w-full rounded-full" />
        </div>
      ) : !result || result.basket.lines.length === 0 ? (
        <EmptyBasket />
      ) : (
        <FilledBasket result={result} />
      )}
    </section>
  );
}

function EmptyBasket() {
  return (
    <div className="grid flex-1 place-items-center py-10 text-center">
      <div>
        <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full bg-elevated text-muted">
          <ShoppingCart size={18} />
        </div>
        <p className="text-sm font-medium">Your basket will appear here.</p>
        <p className="mx-auto mt-1 max-w-xs text-xs text-muted">
          Ask for anything — groceries, snacks, electronics — and the agent builds the basket within
          your budget.
        </p>
      </div>
    </div>
  );
}

function FilledBasket({ result }: { result: DecideResponse }) {
  const b = result.basket;
  const bc = result.budget_check;
  const budget = result.understanding.budget_inr;
  const hasEstimates = b.lines.some((l) => l.estimated);

  const ratio = budget && budget > 0 ? b.total / budget : 0;
  const tone = !budget ? "accent" : bc.within_budget ? "good" : "bad";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Lines */}
      <ul className="scroll-thin -mx-1 max-h-[38vh] space-y-1 overflow-y-auto px-1">
        <AnimatePresence initial>
          {b.lines.map((l, i) => (
            <motion.li
              key={l.offer_id}
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ delay: i * 0.05, type: "spring", stiffness: 300, damping: 28 }}
              className="flex items-center justify-between gap-3 rounded-xl border border-line bg-elevated/50 px-3 py-2.5"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">{l.product_name}</span>
                  {l.estimated && (
                    <span className="inline-flex items-center gap-1 rounded-md bg-warn/15 px-1.5 py-0.5 text-[10px] font-semibold text-warn">
                      <Tag size={9} /> est.
                    </span>
                  )}
                </div>
                <span className="text-xs text-muted">{qtyLabel(l.quantity, l.unit)}</span>
              </div>
              <span className="shrink-0 text-sm font-semibold tabular-nums">
                {money(l.line_total)}
              </span>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>

      {/* Total */}
      <div className="mt-4 flex items-baseline justify-between border-t border-line pt-3">
        <span className="text-sm font-medium text-muted">Total</span>
        <motion.span
          key={b.total}
          initial={{ scale: 0.9, opacity: 0.6 }}
          animate={{ scale: 1, opacity: 1 }}
          className="text-xl font-bold tabular-nums"
        >
          {money(b.total)}
        </motion.span>
      </div>

      {/* Budget progress */}
      {budget != null && (
        <div className="mt-3">
          <div className="mb-1.5 flex items-center justify-between text-xs">
            <span className={bc.within_budget ? "text-good" : "text-bad"}>
              {bc.within_budget ? "Within budget" : "Over budget"}
            </span>
            <span className="text-muted tabular-nums">
              {money(b.total)} / {money(budget)}
            </span>
          </div>
          <ProgressBar value={ratio} tone={tone} />
          {bc.within_budget && bc.remaining_inr != null && (
            <p className="mt-1.5 text-xs text-muted">{money(bc.remaining_inr)} left to spend</p>
          )}
          {!bc.within_budget && bc.over_by_inr != null && (
            <p className="mt-1.5 text-xs text-bad">{money(bc.over_by_inr)} over your budget</p>
          )}
        </div>
      )}

      {/* Options when the agent needs a decision */}
      {result.options_for_user.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
            Options
          </p>
          <ul className="space-y-1.5">
            {result.options_for_user.map((o) => (
              <li
                key={o.option}
                className="flex items-center justify-between gap-3 rounded-lg border border-line bg-surface px-3 py-2 text-sm"
              >
                <span className="min-w-0 truncate">{o.option}</span>
                <span className="shrink-0 tabular-nums text-muted">{money(o.resulting_total)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasEstimates && (
        <p className="mt-3 flex items-start gap-1.5 text-xs text-muted">
          <Info size={13} className="mt-0.5 shrink-0" />
          Prices marked “est.” are the agent’s market estimates (no live retail price source
          connected yet).
        </p>
      )}
    </div>
  );
}
