"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, X, Activity, Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/Skeleton";
import { stateLabel } from "@/lib/labels";
import type { DecideResponse } from "@/lib/api";

type Tone = "good" | "warn" | "bad";

interface Phase {
  label: string;
  detail: string;
  tone: Tone;
}

function buildActivity(r: DecideResponse): Phase[] {
  const n = r.understanding.items.length;
  const phases: Phase[] = [];
  phases.push({
    label: "Understanding your request",
    detail: n
      ? `${n} item(s)${
          r.understanding.budget_inr != null ? ` · budget ₹${r.understanding.budget_inr}` : ""
        }`
      : "no items recognized",
    tone: n ? "good" : "bad",
  });
  if (r.basket.lines.length) {
    phases.push({
      label: "Comparing options & building basket",
      detail: `${r.basket.lines.length} item(s) · ₹${r.basket.total}`,
      tone: "good",
    });
    phases.push({
      label: "Budget check",
      detail: r.budget_check.within_budget
        ? `within budget${
            r.budget_check.remaining_inr != null ? ` · ₹${r.budget_check.remaining_inr} left` : ""
          }`
        : `over by ₹${r.budget_check.over_by_inr}`,
      tone: r.budget_check.within_budget ? "good" : "warn",
    });
  }
  const finalTone: Record<string, Tone> = {
    PROCEED_TO_CHECKOUT: "good",
    ASK_USER: "warn",
    RETRY_SEARCH: "bad",
  };
  phases.push({
    label: stateLabel(r.next_action),
    detail: "",
    tone: finalTone[r.next_action] ?? "good",
  });
  return phases;
}

const DOT: Record<Tone, string> = {
  good: "bg-good/15 text-good",
  warn: "bg-warn/15 text-warn",
  bad: "bg-bad/15 text-bad",
};

export function ActivityTimeline({
  result,
  running,
}: {
  result: DecideResponse | null;
  running: boolean;
}) {
  const phases = result ? buildActivity(result) : [];

  return (
    <section aria-labelledby="activity-heading" className="flex h-full flex-col">
      <div className="mb-4 flex items-center gap-2">
        <Activity size={16} className="text-accent" />
        <h3 id="activity-heading" className="text-sm font-semibold">
          Agent Activity
        </h3>
      </div>

      {running ? (
        <div className="space-y-3" aria-live="polite">
          <div className="flex items-center gap-2 text-sm text-muted">
            <Loader2 size={15} className="animate-spin text-accent" />
            Agent is working…
          </div>
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="h-7 w-7 rounded-full" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-3 w-2/3" />
                <Skeleton className="h-2.5 w-1/3" />
              </div>
            </div>
          ))}
        </div>
      ) : phases.length ? (
        <ol className="relative space-y-1" aria-live="polite">
          <AnimatePresence initial>
            {phases.map((p, i) => (
              <motion.li
                key={`${p.label}-${i}`}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08, type: "spring", stiffness: 300, damping: 26 }}
                className="flex items-start gap-3 py-1.5"
              >
                <span
                  className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full ${DOT[p.tone]}`}
                  aria-hidden="true"
                >
                  {p.tone === "bad" ? <X size={14} /> : <Check size={14} />}
                </span>
                <span className="min-w-0 pt-0.5">
                  <span className="block text-sm font-medium">{p.label}</span>
                  {p.detail && <span className="mt-0.5 block text-xs text-muted">{p.detail}</span>}
                </span>
              </motion.li>
            ))}
          </AnimatePresence>
        </ol>
      ) : (
        <div className="grid flex-1 place-items-center py-10 text-center">
          <div>
            <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full bg-elevated text-muted">
              <Activity size={18} />
            </div>
            <p className="text-sm font-medium">Your agent&apos;s activity will appear here.</p>
            <p className="mx-auto mt-1 max-w-xs text-xs text-muted">
              Submit an instruction to watch the agent understand, build, and budget-check your
              order.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
