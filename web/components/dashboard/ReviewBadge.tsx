"use client";

import { motion } from "framer-motion";
import { ShieldCheck, ShieldAlert, ShieldX, Bot, AlertTriangle } from "lucide-react";
import { ProgressBar } from "@/components/ui/ProgressBar";
import type { DecideReview } from "@/lib/api";

const VERDICT = {
  PASS: {
    label: "Passed review",
    Icon: ShieldCheck,
    icon: "text-good",
    chip: "bg-good/15 text-good",
  },
  PASS_WITH_NOTES: {
    label: "Passed with notes",
    Icon: ShieldAlert,
    icon: "text-warn",
    chip: "bg-warn/15 text-warn",
  },
  FAIL: {
    label: "Needs your call",
    Icon: ShieldX,
    icon: "text-bad",
    chip: "bg-bad/15 text-bad",
  },
};

const AUTOPILOT: Record<string, string> = {
  AUTO_EXECUTE: "Would auto-order (high confidence)",
  EXECUTE_NOTIFY: "Would order & notify you",
  ASK_USER: "Would ask you first",
};

export function ReviewBadge({ review }: { review: DecideReview }) {
  const v = VERDICT[review.verdict as keyof typeof VERDICT] ?? VERDICT.PASS_WITH_NOTES;
  const conf = Math.max(0, Math.min(100, review.confidence));
  const confTone: "good" | "warn" | "bad" = conf >= 85 ? "good" : conf >= 60 ? "warn" : "bad";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26 }}
      className="mt-5 rounded-xl border border-line bg-elevated/40 p-4"
    >
      <div className="flex items-center gap-2">
        <v.Icon size={16} className={v.icon} />
        <span className="text-sm font-semibold">Self-review</span>
        <span className={`ml-auto rounded-md px-2 py-0.5 text-[11px] font-semibold ${v.chip}`}>
          {v.label}
        </span>
      </div>

      <div className="mt-3">
        <div className="mb-1.5 flex items-center justify-between text-xs text-muted">
          <span>Confidence</span>
          <span className="tabular-nums">{conf}/100</span>
        </div>
        <ProgressBar value={conf / 100} tone={confTone} />
      </div>

      <div className="mt-3 flex items-center gap-2 text-xs text-muted">
        <Bot size={14} className="text-accent" />
        <span>Autopilot: {AUTOPILOT[review.autopilot] ?? review.autopilot}</span>
      </div>

      {review.concerns.length > 0 && (
        <ul className="mt-2 space-y-1">
          {review.concerns.map((c) => (
            <li key={c} className="flex items-start gap-1.5 text-xs text-warn">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              {c}
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  );
}
