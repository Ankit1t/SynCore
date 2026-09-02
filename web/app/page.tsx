"use client";

import { useState } from "react";
import { DecideBasket } from "@/components/DecideBasket";
import { Pill } from "@/components/Pill";
import { friendlyError, stateLabel } from "@/lib/labels";
import { askAgent, type DecideResponse } from "@/lib/api";

// Suggestions deliberately mix grocery + non-grocery so it's obvious the agent
// handles ANYTHING an interviewer might ask — not just vegetables.
const SUGGESTIONS = [
  "Order groceries for dinner under ₹500",
  "Order 2 tubs of ice cream and a bluetooth speaker under ₹3,000",
  "Get a phone charger and 1 kg apples under ₹800",
  "Buy a birthday cake and party snacks under ₹1,000",
];

const PLACEHOLDER =
  "Tell your agent what to buy — it will handle the rest.\n\nExample: Order 1 kg of potatoes, 100 g of green chilies, and 2 packs of Maggi within a ₹500 budget.";

interface Phase {
  label: string;
  detail: string;
  tone: "good" | "warn" | "bad";
}

function buildActivity(r: DecideResponse): Phase[] {
  const n = r.understanding.items.length;
  const phases: Phase[] = [];
  phases.push({
    label: "Understanding your request",
    detail: n
      ? `${n} item(s)${r.understanding.budget_inr != null ? ` · budget ₹${r.understanding.budget_inr}` : ""}`
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
        ? `within budget${r.budget_check.remaining_inr != null ? ` · ₹${r.budget_check.remaining_inr} left` : ""}`
        : `over by ₹${r.budget_check.over_by_inr}`,
      tone: r.budget_check.within_budget ? "good" : "warn",
    });
  }
  const finalTone: Record<string, Phase["tone"]> = {
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

const DOT_TONE = { good: "text-good", warn: "text-warn", bad: "text-bad" } as const;

export default function ShopPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<DecideResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go(q?: string) {
    const query = (q ?? text).trim();
    if (!query || running) return; // guard against duplicate submissions
    if (q) setText(q);
    setError(null);
    setResult(null);
    setRunning(true);
    try {
      const res = await askAgent(query);
      setResult(res);
    } catch {
      setError(friendlyError("agent request failed"));
    } finally {
      setRunning(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      go();
    }
  }

  const canSubmit = text.trim().length > 0 && !running;
  const activity = result ? buildActivity(result) : [];
  const nextTone =
    result?.next_action === "PROCEED_TO_CHECKOUT"
      ? "bg-good/15 text-good"
      : result?.next_action === "ASK_USER"
        ? "bg-warn/15 text-warn"
        : "bg-bad/15 text-bad";
  const msgTone = !result
    ? ""
    : result.next_action === "PROCEED_TO_CHECKOUT"
      ? "border-good/40 bg-good/10 text-good"
      : result.next_action === "ASK_USER"
        ? "border-warn/40 bg-warn/10 text-warn"
        : "border-line bg-panel2 text-white/90";

  return (
    <div>
      <section className="mb-6">
        <h2 className="text-2xl font-semibold tracking-tight">What can I get for you?</h2>
        <p className="mt-1 text-sm text-muted">
          Give one instruction — anything, not just groceries. Your agent understands it, builds the
          best basket, and keeps it within your budget.
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
        <div role="alert" className="mb-4 rounded-xl border border-bad/40 bg-bad/10 p-3 text-sm text-bad">
          {error}
        </div>
      )}

      {result?.message_to_user && (
        <div className={`mb-4 rounded-xl border p-3 text-sm ${msgTone}`} aria-live="polite">
          {result.message_to_user}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <section className="card p-4" aria-labelledby="activity-heading">
          <div className="mb-3 flex items-center gap-2">
            <h3 id="activity-heading" className="text-sm font-semibold">
              Agent Activity
            </h3>
            {result && <Pill label={stateLabel(result.next_action)} tone={nextTone} />}
          </div>

          {running ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted">
              <span className="spinner-sm inline-block" aria-hidden="true" />
              Agent is working…
            </div>
          ) : activity.length ? (
            <ol className="m-0 list-none space-y-0 p-0" aria-live="polite">
              {activity.map((p, i) => (
                <li key={i} className="flex gap-3 border-b border-dashed border-line py-2.5 last:border-0">
                  <span className={`mt-0.5 shrink-0 text-[11px] font-bold ${DOT_TONE[p.tone]}`} aria-hidden="true">
                    {p.tone === "bad" ? "✕" : "✓"}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-white/90">{p.label}</span>
                    {p.detail && <span className="mt-0.5 block text-xs text-muted">{p.detail}</span>}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <div className="py-6 text-center">
              <p className="text-sm font-medium text-white/90">Your agent&apos;s activity will appear here.</p>
              <p className="mt-1 text-xs text-muted">
                Submit an instruction to watch the agent work through your order.
              </p>
            </div>
          )}
        </section>

        <section className="card p-4" aria-labelledby="basket-heading">
          <h3 id="basket-heading" className="mb-3 text-sm font-semibold">
            Recommended Basket
          </h3>
          <DecideBasket result={running ? null : result} />
        </section>
      </div>
    </div>
  );
}
