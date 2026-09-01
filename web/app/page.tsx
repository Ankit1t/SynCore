"use client";

import { useRef, useState } from "react";
import { AgentTimeline } from "@/components/AgentTimeline";
import { BasketCard } from "@/components/BasketCard";
import { Pill } from "@/components/Pill";
import { friendlyError, stateLabel } from "@/lib/labels";
import { streamAgentRun, type AgentRun, type Step } from "@/lib/api";

// Suggested instructions — each demonstrates a different agent capability:
// meal/intent, weekly/recurring, multi-item, tight budget, natural language.
const SUGGESTIONS = [
  "Order groceries for dinner under ₹500",
  "Get my weekly groceries within ₹1,500",
  "Buy ingredients for tonight's dinner",
  "Order 2 packs of Maggi and 1 kg of rice under ₹100",
];

const PLACEHOLDER =
  "Tell your agent what to buy — it will handle the rest.\n\nExample: Order 1 kg of potatoes, 100 g of green chilies, and 2 packs of Maggi within a ₹500 budget.";

function stateTone(state: string): string {
  if (["COMPLETED", "CART_VERIFIED", "BASKET_READY", "ORDER_PLACED", "ORDER_VERIFICATION"].includes(state))
    return "bg-good/15 text-good";
  if (["USER_REVIEW_REQUIRED", "PAYMENT_AUTH_REQUIRED", "RECOVERY"].includes(state))
    return "bg-warn/15 text-warn";
  if (["FAILED", "ERROR", "CANCELLED"].includes(state)) return "bg-bad/15 text-bad";
  return "bg-accent/15 text-accent";
}

export default function ShopPage() {
  const [text, setText] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [state, setState] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<null | (() => void)>(null);

  function go(q?: string) {
    const query = (q ?? text).trim();
    if (!query || running) return; // guard prevents duplicate submissions
    if (q) setText(q);
    setSteps([]);
    setRun(null);
    setState("");
    setError(null);
    setRunning(true);
    closeRef.current = streamAgentRun(query, {
      onStep: (s) => {
        setSteps((prev) => [...prev, s]);
        setState(s.state);
      },
      onFinal: (r) => {
        setRun(r);
        setState(r.state);
        setRunning(false);
      },
      onError: (m) => {
        setError(friendlyError(m));
        setState("ERROR");
        setRunning(false);
      },
    });
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter submits; Shift+Enter inserts a newline (modern composer behavior).
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      go();
    }
  }

  const canSubmit = text.trim().length > 0 && !running;

  return (
    <div>
      <section className="mb-6">
        <h2 className="text-2xl font-semibold tracking-tight">What can I get for you?</h2>
        <p className="mt-1 text-sm text-muted">
          Give one instruction. Your agent finds products, compares prices, and builds the best
          basket within your budget — no marketplace searching required.
        </p>
      </section>

      {/* AI composer */}
      <div className="rounded-2xl border border-line bg-panel p-2.5 transition focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/40">
        <label htmlFor="agent-instruction" className="sr-only">
          Instruction for your shopping agent
        </label>
        <textarea
          id="agent-instruction"
          className="block max-h-48 min-h-[92px] w-full resize-none bg-transparent px-3 py-2 text-[15px] leading-relaxed text-white outline-none placeholder:text-muted"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={PLACEHOLDER}
          rows={3}
          aria-describedby="composer-hint"
          disabled={running}
        />
        <div className="flex items-center justify-between gap-3 px-2 pb-1 pt-1">
          <span id="composer-hint" className="text-xs text-muted">
            Press Enter to send · Shift + Enter for a new line
          </span>
          <button
            type="button"
            onClick={() => go()}
            disabled={!canSubmit}
            aria-label={running ? "Agent is working" : "Let the agent handle your instruction"}
            aria-busy={running}
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? (
              <>
                <span className="spinner" aria-hidden="true" />
                Agent is working…
              </>
            ) : (
              <>
                Let Agent Handle It
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M5 12h14M13 6l6 6-6 6"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Suggestions */}
      <div className="mb-6 mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => go(s)}
            disabled={running}
            className="rounded-full border border-line bg-panel2 px-3.5 py-1.5 text-xs text-muted transition hover:border-accent/50 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-bad/40 bg-bad/10 p-3 text-sm text-bad"
        >
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <section className="card p-4" aria-labelledby="activity-heading">
          <div className="mb-3 flex items-center gap-2">
            <h3 id="activity-heading" className="text-sm font-semibold">
              Agent Activity
            </h3>
            {state && !error && <Pill label={stateLabel(state)} tone={stateTone(state)} />}
          </div>
          <AgentTimeline steps={steps} running={running} />
        </section>

        <section className="card p-4" aria-labelledby="basket-heading">
          <h3 id="basket-heading" className="mb-3 text-sm font-semibold">
            Optimized Basket
          </h3>
          <BasketCard basket={run?.basket ?? null} order={run?.order ?? null} />
          {run?.checkpoint_reason && (
            <p className="mt-3 rounded-lg bg-warn/10 p-3 text-sm text-warn">
              Your agent paused for your approval: {stateLabel(run.checkpoint_reason)}.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
