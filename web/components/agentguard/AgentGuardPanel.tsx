"use client";

import { useEffect, useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  Check,
  X,
  Loader2,
  Link2,
  FileSignature,
  ScrollText,
  CreditCard,
  Sparkles,
} from "lucide-react";
import {
  agenticCheckout,
  agenticConfirm,
  getAgenticConfig,
  type AgenticCheckoutResponse,
  type AgenticConfig,
  type PolicyCheck,
} from "@/lib/api";
import { openCheckout } from "@/lib/razorpay";

const PRESETS = [
  "1kg aloo, 100g mirch aur 2 Maggi under ₹500",
  "2 litre milk, 1 dozen eggs, 1 bread under ₹300",
  "5kg atta, 1kg sugar, 1kg rice under ₹600",
];

type Phase = "idle" | "running" | "done" | "paying" | "settled" | "error";

export function AgentGuardPanel() {
  const [text, setText] = useState(PRESETS[0]);
  const [limitInr, setLimitInr] = useState<string>("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [res, setRes] = useState<AgenticCheckoutResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<AgenticConfig | null>(null);
  const [receipt, setReceipt] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    getAgenticConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  async function run() {
    setPhase("running");
    setError(null);
    setRes(null);
    setReceipt(null);
    try {
      const perTxn = limitInr.trim() ? Math.round(parseFloat(limitInr) * 100) : null;
      const r = await agenticCheckout({ text, per_txn_paise: perTxn, human_present: true });
      setRes(r);
      setPhase(r.stage === "SETTLED" ? "settled" : "done");
    } catch (e) {
      setError((e as Error).message);
      setPhase("error");
    }
  }

  async function payLive() {
    if (!res?.checkout) return;
    setPhase("paying");
    setError(null);
    try {
      const c = res.checkout;
      const signed = await openCheckout({
        key: c.key_id,
        amount: c.amount,
        currency: c.currency,
        orderId: c.order_id,
        name: c.name,
        description: c.description,
      });
      const confirmed = await agenticConfirm({
        intent_id: c.intent_id,
        razorpay_order_id: signed.razorpay_order_id,
        razorpay_payment_id: signed.razorpay_payment_id,
        razorpay_signature: signed.razorpay_signature,
      });
      if (confirmed.verified && confirmed.stage === "SETTLED") {
        setReceipt(confirmed.receipt ?? null);
        setPhase("settled");
      } else {
        setError(`payment not settled (${confirmed.stage})`);
        setPhase("error");
      }
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg === "cancelled" ? "Checkout cancelled." : msg);
      setPhase(res ? "done" : "error");
    }
  }

  const decision = res?.decision;
  const chain = res?.ap2_mandates;
  const blocked = res?.stage === "BLOCKED";
  const settled = phase === "settled" || res?.stage === "SETTLED";

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 py-6">
      {/* Header */}
      <header className="space-y-1.5">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-white shadow-glow">
            <ShieldCheck size={18} />
          </div>
          <h1 className="text-lg font-semibold">AgentGuard · AP2 Trust Layer</h1>
        </div>
        <p className="text-sm text-muted">
          Every rupee an agent spends passes one deterministic door:{" "}
          <span className="font-medium text-primary">CAN_PAY()</span>. The agent builds the basket,
          AP2 mandates bind the exact cart, and only an <span className="text-good">ALLOW</span> reaches
          Razorpay.
        </p>
        {config && (
          <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px]">
            <span className="rounded-full border border-line bg-elevated px-2 py-0.5 text-muted">
              provider: <span className="text-primary">{config.provider}</span>
            </span>
            <span
              className={`rounded-full px-2 py-0.5 ${
                config.live_checkout ? "bg-good/15 text-good" : "bg-warn/15 text-warn"
              }`}
            >
              {config.live_checkout ? "live Razorpay checkout ON (test mode)" : "mock settle (no keys)"}
            </span>
          </div>
        )}
      </header>

      {/* Input */}
      <div className="rounded-2xl border border-line bg-surface/60 p-4">
        <label className="mb-1.5 block text-xs font-medium text-muted">Tell your agent what to buy</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={2}
          className="w-full resize-none rounded-xl border border-line bg-elevated px-3 py-2.5 text-sm text-primary outline-none focus-visible:ring-2 focus-visible:ring-accent"
        />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setText(p)}
              className="rounded-full border border-line bg-elevated px-2.5 py-1 text-[11px] text-muted transition-colors hover:border-accent/50 hover:text-primary"
            >
              {p}
            </button>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-muted">
              Per-transaction limit (₹) — set low to force a block
            </label>
            <input
              value={limitInr}
              onChange={(e) => setLimitInr(e.target.value)}
              placeholder="auto"
              inputMode="decimal"
              className="w-36 rounded-lg border border-line bg-elevated px-3 py-2 text-sm text-primary outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
          </div>
          <button
            type="button"
            onClick={run}
            disabled={phase === "running" || !text.trim()}
            className="ml-auto inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white shadow-glow transition-opacity disabled:opacity-50"
          >
            {phase === "running" ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            Run agent through the gate
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{error}</div>
      )}

      {res?.stage === "BASKET_NOT_PAYABLE" && (
        <div className="rounded-xl border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
          Agent stopped before payment: {res.reason}
        </div>
      )}

      {/* Decision banner */}
      {decision && (
        <DecisionBanner outcome={decision.outcome} ruleFired={decision.rule_fired} blocked={blocked} settled={settled} />
      )}

      {/* Basket */}
      {res?.basket && (
        <Section title="Basket the agent built" icon={<ScrollText size={15} />}>
          <ul className="divide-y divide-line text-sm">
            {res.basket.items.map((it, i) => (
              <li key={i} className="flex items-center justify-between py-1.5">
                <span className="text-primary">
                  {it.packs}× {it.title}
                </span>
                <span className="tabular-nums text-muted">₹{it.line_total.toFixed(2)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-2 flex items-center justify-between border-t border-line pt-2 text-sm font-medium">
            <span>Total</span>
            <span className="tabular-nums">₹{res.basket.total.toFixed(2)}</span>
          </div>
        </Section>
      )}

      {/* AP2 mandate chain */}
      {chain && (
        <Section title="AP2 mandate chain (verifiable evidence)" icon={<FileSignature size={15} />}>
          <div className="space-y-2">
            <MandateCard
              label="IntentMandate"
              subtitle="user authority + rules"
              digest={chain.intent_mandate.content_digest}
            />
            <ChainLink />
            <MandateCard
              label="CartMandate"
              subtitle={`exact cart · hash ${short(chain.cart_mandate.cart_hash)}`}
              digest={chain.cart_mandate.content_digest}
            />
            {chain.payment_mandate && (
              <>
                <ChainLink />
                <MandateCard
                  label="PaymentMandate"
                  subtitle={`${chain.payment_mandate.policy_outcome} · ₹${chain.payment_mandate.amount}`}
                  digest={chain.payment_mandate.content_digest}
                />
              </>
            )}
          </div>
        </Section>
      )}

      {/* CAN_PAY checks */}
      {decision?.checks?.length ? (
        <Section title="CAN_PAY() — deterministic policy checks" icon={<ShieldCheck size={15} />}>
          <ol className="space-y-1">
            {decision.checks.map((c) => (
              <CheckRow key={c.name} check={c} fired={c.name === decision.rule_fired} />
            ))}
          </ol>
        </Section>
      ) : null}

      {/* Live pay / settled */}
      {res?.stage === "CHECKOUT_REQUIRED" && phase !== "settled" && (
        <button
          type="button"
          onClick={payLive}
          disabled={phase === "paying"}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-good px-4 py-3 text-sm font-semibold text-white transition-opacity disabled:opacity-50"
        >
          {phase === "paying" ? <Loader2 size={16} className="animate-spin" /> : <CreditCard size={16} />}
          Pay ₹{(res.checkout!.amount / 100).toFixed(2)} with UPI (Razorpay test)
        </button>
      )}

      {settled && (
        <div className="rounded-xl border border-good/40 bg-good/10 px-4 py-3 text-sm text-good">
          <div className="flex items-center gap-2 font-semibold">
            <Check size={16} /> Payment settled — order placed.
          </div>
          {config?.provider === "mock" && (
            <p className="mt-1 text-good/80">Autonomous settle via sandbox provider (no real money moved).</p>
          )}
          {receipt && (
            <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-black/20 p-2 text-[11px] text-good/90">
              {JSON.stringify(receipt, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

/* ---------- small building blocks ---------- */

function DecisionBanner({
  outcome,
  ruleFired,
  blocked,
  settled,
}: {
  outcome: string;
  ruleFired: string | null;
  blocked: boolean;
  settled: boolean;
}) {
  const allow = outcome === "ALLOW";
  const challenge = outcome === "REQUIRES_USER_AUTHORIZATION";
  const Icon = allow ? ShieldCheck : challenge ? ShieldQuestion : ShieldAlert;
  // Explicit class strings (Tailwind cannot see dynamically built class names).
  const styles = allow
    ? { box: "border-good/40 bg-good/10", icon: "text-good", title: "text-good" }
    : challenge
      ? { box: "border-warn/40 bg-warn/10", icon: "text-warn", title: "text-warn" }
      : { box: "border-bad/40 bg-bad/10", icon: "text-bad", title: "text-bad" };
  const title = allow
    ? settled
      ? "ALLOW — payment authorized & settled"
      : "ALLOW — payment authorized"
    : challenge
      ? "CHALLENGE — user confirmation required"
      : "DENY — payment blocked by the gate";
  return (
    <div className={`flex items-start gap-3 rounded-2xl border px-4 py-3 ${styles.box}`}>
      <Icon size={20} className={`${styles.icon} mt-0.5 shrink-0`} />
      <div>
        <p className={`text-sm font-semibold ${styles.title}`}>{title}</p>
        {blocked && ruleFired && (
          <p className="text-xs text-muted">
            Stopped at rule <span className="font-mono text-primary">{ruleFired}</span> — the agent could not
            spend beyond your rules.
          </p>
        )}
      </div>
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-surface/60 p-4">
      <h2 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-primary">
        <span className="text-accent">{icon}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function MandateCard({ label, subtitle, digest }: { label: string; subtitle: string; digest: string }) {
  return (
    <div className="rounded-xl border border-line bg-elevated px-3 py-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-primary">{label}</span>
        <span className="text-[11px] text-muted">{subtitle}</span>
      </div>
      <p className="mt-0.5 truncate font-mono text-[11px] text-muted" title={digest}>
        {digest}
      </p>
    </div>
  );
}

function ChainLink() {
  return (
    <div className="flex items-center justify-center py-0.5 text-muted">
      <Link2 size={13} />
    </div>
  );
}

function CheckRow({ check, fired }: { check: PolicyCheck; fired: boolean }) {
  return (
    <li
      className={`flex items-center gap-2 rounded-lg px-2 py-1 text-sm ${
        fired ? "bg-bad/10" : ""
      }`}
    >
      {check.passed ? (
        <Check size={14} className="shrink-0 text-good" />
      ) : (
        <X size={14} className="shrink-0 text-bad" />
      )}
      <span className={`font-mono text-xs ${check.passed ? "text-primary" : "text-bad"}`}>{check.name}</span>
      {!check.passed && <span className="truncate text-[11px] text-muted">— {check.detail}</span>}
    </li>
  );
}

function short(hash: string): string {
  if (!hash) return "—";
  const h = hash.replace("sha256:", "");
  return `${h.slice(0, 6)}…${h.slice(-4)}`;
}
