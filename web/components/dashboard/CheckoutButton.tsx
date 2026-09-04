"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { CreditCard, Loader2, CheckCircle2, Lock } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { createOrder, getPaymentConfig, verifyPayment } from "@/lib/api";

// Minimal typing for the Razorpay checkout global.
declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

const money = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
const CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

function loadRazorpay(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === "undefined") return resolve(false);
    if (window.Razorpay) return resolve(true);
    const s = document.createElement("script");
    s.src = CHECKOUT_SRC;
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

type Status = "idle" | "working" | "paid" | "error";

export function CheckoutButton({ amountInr }: { amountInr: number }) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [note, setNote] = useState("");

  useEffect(() => {
    let active = true;
    getPaymentConfig()
      .then((c) => active && setEnabled(c.enabled))
      .catch(() => active && setEnabled(false));
    return () => {
      active = false;
    };
  }, []);

  async function pay() {
    setStatus("working");
    setNote("");
    try {
      const order = await createOrder(amountInr);
      if (!order.enabled) {
        setEnabled(false);
        setStatus("idle");
        return;
      }
      if (!order.ok || !order.order_id || !order.key_id) {
        throw new Error(order.error || "could not create order");
      }
      const ok = await loadRazorpay();
      if (!ok || !window.Razorpay) throw new Error("could not load checkout");

      const rzp = new window.Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency ?? "INR",
        name: "SynCore",
        description: "AI Shopping Assistant — test order",
        order_id: order.order_id,
        theme: { color: "#6366f1" },
        handler: async (resp: {
          razorpay_order_id: string;
          razorpay_payment_id: string;
          razorpay_signature: string;
        }) => {
          try {
            const { verified } = await verifyPayment(resp);
            setStatus(verified ? "paid" : "error");
            setNote(verified ? "" : "signature verification failed");
          } catch {
            setStatus("error");
            setNote("verification error");
          }
        },
        modal: {
          ondismiss: () => setStatus("idle"),
        },
      });
      rzp.open();
    } catch (e) {
      setStatus("error");
      setNote(e instanceof Error ? e.message : "payment error");
    }
  }

  if (enabled === false) {
    return (
      <p className="mt-4 flex items-center gap-1.5 text-xs text-muted">
        <Lock size={12} className="shrink-0" />
        Payment (Razorpay test mode) not configured on the server.
      </p>
    );
  }

  if (status === "paid") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-4 flex items-center gap-2 rounded-xl border border-good/40 bg-good/10 p-3 text-sm text-good"
      >
        <CheckCircle2 size={16} />
        Payment successful (test mode) — order confirmed.
      </motion.div>
    );
  }

  return (
    <div className="mt-4">
      <Button onClick={pay} disabled={enabled === null || status === "working"} className="w-full">
        {status === "working" ? (
          <>
            <Loader2 size={16} className="animate-spin" /> Processing…
          </>
        ) : (
          <>
            <CreditCard size={16} /> Pay {money(amountInr)} (Test)
          </>
        )}
      </Button>
      {status === "error" && (
        <p className="mt-1.5 text-xs text-bad">Payment failed{note ? `: ${note}` : ""}. Try again.</p>
      )}
      <p className="mt-1.5 flex items-center gap-1 text-[11px] text-muted">
        <Lock size={11} /> Secure test checkout · no real money · card 4111 1111 1111 1111
      </p>
    </div>
  );
}
