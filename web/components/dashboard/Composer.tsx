"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

const SUGGESTIONS = [
  "Order groceries for dinner under ₹500",
  "Order 2 tubs of ice cream and a bluetooth speaker under ₹3,000",
  "Get a phone charger and 1 kg apples under ₹800",
  "Buy some chips and cookies under ₹60",
];

const PLACEHOLDER =
  "Tell your agent what to buy — anything, not just groceries.\nExample: 1 kg potatoes, 100 g green chillies and 2 packs of Maggi under ₹500.";

export function Composer({
  running,
  onSubmit,
}: {
  running: boolean;
  onSubmit: (query: string) => void;
}) {
  const [text, setText] = useState("");
  const canSubmit = text.trim().length > 0 && !running;

  function submit(q?: string) {
    const query = (q ?? text).trim();
    if (!query || running) return;
    onSubmit(query);
    if (!q) setText("");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 26 }}
        className="rounded-2xl border border-line bg-surface p-2.5 shadow-soft transition-colors focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/30"
      >
        <label htmlFor="composer" className="sr-only">
          What can I get for you?
        </label>
        <textarea
          id="composer"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={running}
          rows={3}
          placeholder={PLACEHOLDER}
          className="block max-h-52 min-h-[92px] w-full resize-none bg-transparent px-3 py-2 text-[15px] leading-relaxed text-primary outline-none placeholder:text-muted disabled:opacity-60"
        />
        <div className="flex items-center justify-between gap-3 px-2 pb-1">
          <span className="hidden text-xs text-muted sm:block">
            Enter to send · Shift + Enter for a new line
          </span>
          <Button
            onClick={() => submit()}
            disabled={!canSubmit}
            aria-busy={running}
            className="ml-auto"
          >
            {running ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Working…
              </>
            ) : (
              <>
                Let Agent Handle It
                <ArrowRight size={16} />
              </>
            )}
          </Button>
        </div>
      </motion.div>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s, i) => (
          <motion.button
            key={s}
            type="button"
            onClick={() => submit(s)}
            disabled={running}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i }}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="rounded-full border border-line bg-surface px-3.5 py-1.5 text-xs text-muted transition-colors hover:border-accent/50 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50"
          >
            {s}
          </motion.button>
        ))}
      </div>
    </div>
  );
}
