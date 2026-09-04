"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Wallet, Loader2, CheckCircle2, Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useWallet } from "@/components/wallet/WalletProvider";

const money = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

type Status = "idle" | "paying" | "paid" | "error";

export function CheckoutButton({ amountInr }: { amountInr: number }) {
  const { wallet, loading, payFromWallet, topUp } = useWallet();
  const [status, setStatus] = useState<Status>("idle");
  const [note, setNote] = useState("");

  const balance = wallet?.balance_inr ?? null;
  const funded = balance != null && balance >= amountInr;
  const topupAmt = balance == null ? 5000 : Math.max(500, Math.ceil((amountInr - balance) / 500) * 500);

  async function payNow() {
    setStatus("paying");
    setNote("");
    const res = await payFromWallet(amountInr, "SynCore order");
    if (res.paid) {
      setStatus("paid");
    } else {
      setStatus("error");
      setNote(res.reason === "insufficient balance" ? "insufficient wallet balance" : res.reason ?? "");
    }
  }

  async function addMoney() {
    setStatus("idle");
    await topUp(topupAmt);
  }

  if (status === "paid") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-4 rounded-xl border border-good/40 bg-good/10 p-3 text-sm text-good"
      >
        <div className="flex items-center gap-2 font-medium">
          <CheckCircle2 size={16} /> Order confirmed — paid from wallet.
        </div>
        {wallet && (
          <p className="mt-1 text-xs text-good/80">
            No payment step needed. Wallet balance: {money(wallet.balance_inr)}
          </p>
        )}
      </motion.div>
    );
  }

  return (
    <div className="mt-4">
      {funded ? (
        <Button onClick={payNow} disabled={status === "paying"} className="w-full">
          {status === "paying" ? (
            <>
              <Loader2 size={16} className="animate-spin" /> Paying from wallet…
            </>
          ) : (
            <>
              <Wallet size={16} /> Pay {money(amountInr)} from Wallet
            </>
          )}
        </Button>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-warn">
            Wallet balance {balance != null ? money(balance) : "—"} is less than {money(amountInr)}.
          </p>
          <Button onClick={addMoney} disabled={loading} variant="subtle" className="w-full">
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Opening top-up…
              </>
            ) : (
              <>
                <Plus size={16} /> Top up {money(topupAmt)} (Razorpay test)
              </>
            )}
          </Button>
        </div>
      )}

      {status === "error" && (
        <p className="mt-1.5 text-xs text-bad">Payment failed{note ? `: ${note}` : ""}.</p>
      )}
      <p className="mt-1.5 flex items-center gap-1 text-[11px] text-muted">
        <Wallet size={11} /> Paid instantly from your prepaid wallet — no gateway step per order.
      </p>
    </div>
  );
}
