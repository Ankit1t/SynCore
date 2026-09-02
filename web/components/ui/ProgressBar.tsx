"use client";

import { motion } from "framer-motion";

type Tone = "accent" | "good" | "warn" | "bad";

const TONE: Record<Tone, string> = {
  accent: "bg-accent",
  good: "bg-good",
  warn: "bg-warn",
  bad: "bg-bad",
};

/**
 * Animated horizontal progress bar. `value` is clamped 0..1.
 */
export function ProgressBar({
  value,
  tone = "accent",
  className = "",
}: {
  value: number;
  tone?: Tone;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div
      className={`h-2 w-full overflow-hidden rounded-full bg-elevated ${className}`}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <motion.div
        className={`h-full rounded-full ${TONE[tone]}`}
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ type: "spring", stiffness: 120, damping: 20 }}
      />
    </div>
  );
}
