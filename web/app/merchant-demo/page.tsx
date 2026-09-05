"use client";

import { useState } from "react";
import { Store, PackageCheck, ShieldAlert, Loader2, Sparkles, Check, X } from "lucide-react";
import { agenticCheckout, type Ap2Chain } from "@/lib/api";
import { verifyMandate, type MerchantVerifyResult } from "@/lib/merchant-sdk";

export default function MerchantDemoPage() {
  const [chain, setChain] = useState<Ap2Chain | null>(null);
  const [cartTotal, setCartTotal] = useState<string>("");
  const [tamper, setTamper] = useState(false);
  const [result, setResult] = useState<MerchantVerifyResult | null>(null);
  const [phase, setPhase] = useState<"idle" | "getting" | "verifying" | "done">("idle");
  const [error, setError] = useState<string | null>(null);

  async function getMandate() {
    setPhase("getting");
    setError(null);
    setResult(null);
    setChain(null);
    try {
      const r = await agenticCheckout({ text: "2 litre milk, 1 dozen eggs, 1 bread under 300" });
      if (!r.ap2_mandates) throw new Error(`agent returned stage ${r.stage}, no mandate`);
      setChain(r.ap2_mandates);
      setCartTotal((r.ap2_mandates.cart_mandate.total_amount as string) ?? "");
      setPhase("idle");
    } catch (e) {
      setError((e as Error).message);
      setPhase("idle");
    }
  }

  async function verify() {
    if (!chain) return;
    setPhase("verifying");
    setError(null);
    try {
      // A merchant receives the chain and verifies it before fulfilling.
      let payload: Ap2Chain = chain;
      if (tamper) {
        // Simulate a malicious agent inflating the cart after the user signed it.
        payload = JSON.parse(JSON.stringify(chain));
        const cm = payload.cart_mandate as unknown as { total_paise: number; total_amount: string };
        cm.total_paise += 500000;
        cm.total_amount = "9999.00";
      }
      const res = await verifyMandate(payload);
      setResult(res);
      setPhase("done");
    } catch (e) {
      setError((e as Error).message);
      setPhase("idle");
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 py-6">
      <header className="space-y-1.5">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-white shadow-glow">
            <Store size={18} />
          </div>
          <h1 className="text-lg font-semibold">Merchant SDK Demo</h1>
        </div>
        <p className="text-sm text-muted">
          A merchant receives a signed AP2 CartMandate from a shopping agent. Before shipping, the
          drop-in <span className="font-mono text-primary">merchant-sdk</span> verifies the chain
          links and Ed25519 signatures. Ship only if it verifies.
        </p>
      </header>

      {/* Step 1 */}
      <section className="rounded-2xl border border-line bg-surface/60 p-4">
        <p className="mb-2 text-sm font-semibold">1 · Receive a signed cart mandate from the agent</p>
        <button
          type="button"
          onClick={getMandate}
          disabled={phase === "getting"}
          className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white shadow-glow disabled:opacity-50"
        >
          {phase === "getting" ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
          Request agentic cart
        </button>

        {chain && (
          <div className="mt-3 space-y-1.5 rounded-xl border border-line bg-elevated p-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted">merchant</span>
              <span>{chain.cart_mandate.merchant_id as string}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">total</span>
              <span>₹{cartTotal}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">cart_hash</span>
              <span className="font-mono text-[11px]">{(chain.cart_mandate.cart_hash as string)?.slice(0, 18)}…</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">signed by</span>
              <span className="font-mono text-[11px]">{(chain.cart_mandate as { signer_id?: string }).signer_id}</span>
            </div>
          </div>
        )}
      </section>

      {/* Step 2 */}
      {chain && (
        <section className="rounded-2xl border border-line bg-surface/60 p-4">
          <p className="mb-2 text-sm font-semibold">2 · Verify with the SDK, then fulfil</p>
          <label className="mb-3 flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={tamper} onChange={(e) => setTamper(e.target.checked)} />
            Simulate a tampered cart (agent inflates the amount after signing)
          </label>
          <button
            type="button"
            onClick={verify}
            disabled={phase === "verifying"}
            className="inline-flex items-center gap-2 rounded-xl bg-good px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {phase === "verifying" ? <Loader2 size={16} className="animate-spin" /> : <PackageCheck size={16} />}
            Verify &amp; fulfil order
          </button>
        </section>
      )}

      {error && (
        <div className="rounded-xl border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{error}</div>
      )}

      {/* Result */}
      {result && (
        <section
          className={`rounded-2xl border p-4 ${
            result.ok ? "border-good/40 bg-good/10" : "border-bad/40 bg-bad/10"
          }`}
        >
          <div className={`flex items-center gap-2 text-sm font-semibold ${result.ok ? "text-good" : "text-bad"}`}>
            {result.ok ? <PackageCheck size={18} /> : <ShieldAlert size={18} />}
            {result.ok ? "Verified — order fulfilled" : "Rejected — NOT fulfilled"}
          </div>

          <div className="mt-3 space-y-2 text-sm">
            <div>
              <p className="text-xs font-medium text-muted">Local chain-link check (offline)</p>
              <ul className="mt-1 space-y-0.5">
                {result.local.details.map((d, i) => (
                  <li key={i} className="flex items-center gap-1.5 text-[13px]">
                    <span className={result.local.links_ok ? "text-good" : "text-muted"}>·</span> {d}
                  </li>
                ))}
              </ul>
            </div>
            {result.server && (
              <div className="flex items-center gap-2 text-[13px]">
                <span className="text-xs font-medium text-muted">Server signature check:</span>
                {result.server.ok ? (
                  <span className="inline-flex items-center gap-1 text-good"><Check size={13} /> valid</span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-bad"><X size={13} /> invalid</span>
                )}
              </div>
            )}
            {result.reason && <p className="text-xs text-bad">{result.reason}</p>}
          </div>
        </section>
      )}
    </div>
  );
}
